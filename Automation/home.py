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

try:
    from systemd.journal import JournalHandler
    logger = logging.getLogger(appName)
    logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER=appName))
except ImportError:
    logger = logging.getLogger(appName)
    stdout = logging.StreamHandler(sys.stdout)
    logger.addHandler(stdout)
finally:
    logger.setLevel(logging.INFO)

global args, state

class State:
    temperatureKitchen = -1
    powerTV = -1
    timerTV = -1

def on_connect(client, userdata, flags, rc):
  logger.debug("Connected with result code "+str(rc))
  client.subscribe([("zigbee2mqtt/#",0)])

def on_message_http(client, userdata, msg):
    global args
    logger.debug(msg.payload.decode())
    logger.debug(Sensors)
    logger.debug(msg.topic)
    client.publish("test/automation","""{"state":"on"}""")

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
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
