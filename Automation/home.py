#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import socket
import json
import time
import datetime
import logging
import traceback
import sys
import argparse
import requests
from requests.auth import HTTPBasicAuth
import re

appName = 'homeAutomation'

if False:
    logger = logging.getLogger(appName)
    stdout = logging.StreamHandler(sys.stdout)
    logger.addHandler(stdout)
    logger.setLevel(logging.INFO)
else:
    try:
        from systemd.journal import JournalHandler
        logger = logging.getLogger(appName)
        logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER=appName))
    except ImportError:
        logger = logging.getLogger(appName)
        stdout = logging.StreamHandler(sys.stdout)
        logger.addHandler(stdout)
    finally:
        logger.setLevel(logging.DEBUG)

global args, state

class State:
    heatingKitchen = None
    heatingRate = 0.10 # deg/min
    heatingDelay = 15 * 60 # # seconds
    heatingKitchenStart = (6, 0) # (hour, minute)
    heatingKitchenEnd = (8, 30) # (hour, minute)
    heatingKitchenWantedTime = (7, 45)
    heatingKitchenNightStart = (20, 0)
    heatingKitchenNightEnd = heatingKitchenStart
    temperatureKitchen = None
    temperatureThreshold = 18.5 # deg
    temperatureHysteresis = 0.5 # deg
    powerTV = None
    lastOnTV = None
    sleepTime = 60 * 10 # 10 min

    def format(o):
        if type(o) is datetime.date or type(o) is datetime.datetime:
            return o.isoformat()
        else:
            return str(o)

    def json(self):
        return  json.dumps(self.__dict__, sort_keys=True, default=format, separators=(',', ':'))

def on_connect(client, userdata, flags, rc):
  logger.debug("Connected with result code "+str(rc))
  client.subscribe([("zigbee2mqtt/#",0)])

def on_message_http(client, userdata, msg):
    global args, state

    if msg.topic == "zigbee2mqtt/living-room-socket-tv":
        logger.debug("living-room-socket-tv: " + msg.payload.decode())
        try:
            payload = json.loads(msg.payload.decode())
        except:
            logger.error("Cannot parse json \"%s\""%msg.payload.decode())
            pass
        else:
            if state.powerTV is None or float(payload['power']) > 50.0:
                state.powerTV = float(payload['power']) > 50.0
                state.lastOnTV = datetime.datetime.now()

            if state.powerTV:
                state.lastOnTV = datetime.datetime.now()

            if (datetime.datetime.now() - state.lastOnTV).total_seconds() > state.sleepTime and payload['state'].lower() == "on":
                logger.info("Turning off TV")
                state.powerTV = False
                state.lastOnTV = datetime.datetime.now()
                client.publish("zigbee2mqtt/living-room-socket-tv/set","""{"state":"off"}""")

    elif msg.topic == "zigbee2mqtt/kitchen-sensor1":
        logger.debug("kitchen-sensor1: " + msg.payload.decode())
       	try:
            payload = json.loads(msg.payload.decode())
       	except:
            logger.error("Cannot parse json \"%s\""%msg.payload.decode())
            pass
       	else:
            state.temperatureKitchen = float(payload['temperature'])

            # switching on heating in morning when needed
            now = datetime.datetime.now()
            start = now.replace(hour=state.heatingKitchenStart[0], minute=state.heatingKitchenStart[1], second=0)
            end = now.replace(hour=state.heatingKitchenWantedTime[0], minute=state.heatingKitchenWantedTime[1], second=0)
            if  (now > start and now < end and not state.heatingKitchen):
                duration = (end - now).total_seconds()
                needed = ((state.temperatureThreshold - state.temperatureHysteresis) - state.temperatureKitchen) / state.heatingRate * 60 + state.heatingDelay
                logger.debug("%d seconds before end time, %d seconds needed. temperature/threshold: %f/%f"%(duration, needed, state.temperatureKitchen, state.temperatureThreshold - state.temperatureHysteresis))
                if duration <= needed:
                    logger.info("Switching kitchen heating on")
                    client.publish("zigbee2mqtt/kitchen-socket2/set","""{"state":"on"}""")

    elif msg.topic == "zigbee2mqtt/kitchen-socket2":
        logger.debug("kitchen-socket2: " + msg.payload.decode())
        try:
            payload = json.loads(msg.payload.decode())
        except:
            logger.error("Cannot parse json \"%s\""%msg.payload.decode())
            return

        # enforce heating off overnight
        now = datetime.datetime.now()
        todayNightStart = now.replace(hour=state.heatingKitchenNightStart[0], minute=state.heatingKitchenNightStart[1], second=0, microsecond=0)
        todayNightEnd = now.replace(hour=state.heatingKitchenNightEnd[0], minute=state.heatingKitchenNightEnd[1], second=0, microsecond=0)
        if payload['state'].lower() == "on" and (now > todayNightStart or now < todayNightEnd):
            state.heatingKitchen = false
            logger.info("Switching kitchen heating off, it should not be on overnight")
            client.publish("zigbee2mqtt/kitchen-socket2/set","""{"state":"off"}""")

        # enforce switching heating off after heatingKitchenEnd
        now = datetime.datetime.now()
        todayMorning = now.replace(hour=state.heatingKitchenEnd[0], minute=state.heatingKitchenEnd[1], second=0, microsecond=0)
        if payload['state'].lower() == "on" and (now - todayMorning).total_seconds() > 0 and (now - todayMorning).total_seconds() < 60.0:
            state.heatingKitchen = false
            logger.info("Switching kitchen heating off, overunning morning setting")
            client.publish("zigbee2mqtt/kitchen-socket2/set","""{"state":"off"}""")

        if state.temperatureKitchen is not None:
            state.heatingKitchen = payload['state'].lower() == "on"
            if (state.heatingKitchen and state.temperatureKitchen >= state.temperatureThreshold + state.temperatureHysteresis):
                logger.info("Turning off kitchen heating, temperature reached threshold %d"%state.temperatureThreshold)
                client.publish("zigbee2mqtt/kitchen-socket2/set","""{"state":"off"}""")
                state.heatingKitchen = false


def on_publish(client,userdata,result):
    logger.debug("data `%s` published \n"%userdata)

def main():
    global args, token
    parser = argparse.ArgumentParser(description='subscribe to topics and send data to graphite')
    parser.add_argument('--graphiteKey', metavar='GRAPHITEKEY', required=True,
                        help='graphite key')
    parser.add_argument('--graphiteUrl', metavar='GRAPHITEURL', default="https://graphite.debroglie.net/graphiteSink.php",
                        help='graphite host')
    parser.add_argument('--mqttHost', metavar='MQTTHOST', default="localhost",
                        help='mqtt host')
    parser.add_argument('--mqttPort', metavar='MQTTPORT', default=1883,
                        help='mqtt port', type=int)
    args = parser.parse_args()

    token = args.graphiteKey

    client = mqtt.Client()
    client.connect(args.mqttHost,args.mqttPort,60)

    client.on_connect = on_connect
    client.on_message = on_message_http
    client.on_publish = on_publish

    client.loop_forever()

if __name__ == '__main__':
    try:
        state = State()
        logger.debug("Starting app with state: %s"%state.json())
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
