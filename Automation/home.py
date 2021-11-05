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
    logger.setLevel(logging.DEBUG)
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
    heatingRate = 0.15 # deg/min
    heatingKitchenStart = (6, 0) # (hour, minute)
    heatingKitchenEnd = (8, 30) # (hour, minute)
    temperatureKitchen = None
    temperatureThreshold = 19.0
    powerTV = None
    lastOnTV = None
    sleepTime = 60 * 10 # seconds

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
    #logger.debug(msg.payload.decode())
    #logger.debug(msg.topic)

    if msg.topic == "zigbee2mqtt/living-room-socket-tv":
        logger.debug(msg.payload.decode())
        try:
            payload = json.loads(msg.payload.decode())
        except:
            logger.error("Cannot parse json \"%s\""%msg.payload.decode())
            pass
        else:
            if state.powerTV is None or float(payload['power']) > 50.0:
                state.powerTV = float(payload['power']) > 50.0
                state.lastOnTV = datetime.datetime.now()

            if float(payload['power']) < 50.0 and state.powerTV:
                state.powerTV = False
                state.lastOnTV = datetime.datetime.now()

            if (datetime.datetime.now() - state.lastOnTV).total_seconds() > state.sleepTime and payload['state'].lower() == "on":
                logger.info("Turning off TV")
                state.powerTV = False
                state.lastOnTV = datetime.datetime.now()
                client.publish("zigbee2mqtt/living-room-socket-tv/set","""{"state":"off"}""")

    elif msg.topic == "zigbee2mqtt/kitchen-sensor1":
        logger.debug(msg.payload.decode())
       	try:
            payload = json.loads(msg.payload.decode())
       	except:
            logger.error("Cannot parse json \"%s\""%msg.payload.decode())
            pass
       	else:
            state.temperatureKitchen = float(payload['temperature'])

            now = datetime.datetime.now()
            start = now.replace(hour=state.heatingKitchenStart[0], minute=state.heatingKitchenStart[1], second=0)
            end = now.replace(hour=state.heatingKitchenEnd[0], minute=state.heatingKitchenEnd[1], second=0)
            if  (now > start and now < end):
                duration = (end - now).total_seconds()
                needed = (state.temperatureThreshold - state.temperatureKitchen) / state.heatingRate * 60
                logger.debug("%d seconds before end time, %d seconds needed"%(duration, needed))
                if duration <= needed:
                    logger.info("Switching kitchen heating on")
                    client.publish("zigbee2mqtt/kitchen-socket2/set","""{"state":"on"}""")

    elif msg.topic == "zigbee2mqtt/kitchen-socket2":
        if state.temperatureKitchen is not None:
            logger.debug(msg.payload.decode())
            try:
                payload = json.loads(msg.payload.decode())
       	    except:
                logger.error("Cannot parse json \"%s\""%msg.payload.decode())
                pass
            else:
                logger.debug("State: %s"%(state.json()))
                state.heatingKitchen = payload['state'].lower() == "on"
                if (payload['state'].lower() == "on" and state.temperatureKitchen >= state.temperatureThreshold):
                    logger.info("Turning off kitchen heating")
                    client.publish("zigbee2mqtt/kitchen-socket2/set","""{"state":"off"}""")

    logger.debug("State: %s"%(state.json()))

def on_publish(client,userdata,result):             #create function for callback
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
