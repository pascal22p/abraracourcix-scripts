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

appName = 'owntracks2mysql'

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

global Users, LastTimeSent, args, args

Users = ["IphonePascal"]

def sendLocation(payload, mysqlUrl, mysqlUser, mysqlPassword, mysqlDatabase):
    resp = requests.post(
        mysqlUrl,
        json=payload,
        params={'database': mysqlDatabase},
        auth=(mysqlUser, mysqlPassword))
    if resp.status_code == 200:
        logger.info("%s location stored in MySQL"%resp.content.decode())
    else:
        logger.info("Location could not be sent for storage in MySQL: `%s`"%resp.content.decode())
        resp.raise_for_status()

def sendSteps(payload, mysqlUrl, mysqlUser, mysqlPassword, mysqlDatabase):
    resp = requests.post(
        mysqlUrl,
        json=payload,
        params={'database': mysqlDatabase},
        auth=(mysqlUser, mysqlPassword))
    if resp.status_code == 200:
        logger.info("%s steps stored in MySQL"%resp.content.decode())
    else:
        logger.info("Steps could not be sent for storage in MySQL: `%s`"%resp.content.decode())
        resp.raise_for_status()

def on_connect(client, userdata, flags, rc):
    logger.debug("Connected with result code "+str(rc))
    client.subscribe([("owntracks/#",0)])

def on_message_http(client, userdata, msg):
    global args
    logger.debug(msg.payload.decode())
    logger.debug(Users)
    logger.debug(msg.topic)
    for user in Users:
        if user in msg.topic:
            try:
                payload = json.loads(msg.payload.decode())
            except:
                logger.error("Cannot parse json \"%s\""%msg.payload.decode())
                continue
            if (payload["_type"].lower() == "location"):
                sendLocation(payload, args.mysqlLocationUrl, args.mysqlUser, args.mysqlPassword, args.mysqlDatabase)
            elif (payload["_type"].lower() == "steps"):
                sendSteps(payload, args.mysqlStepsUrl, args.mysqlUser, args.mysqlPassword, args.mysqlDatabase)

def main():
    global args
    parser = argparse.ArgumentParser(description='subscribe to topics and send data to graphite')
    parser.add_argument('--mqttHost', metavar='MQTTHOST', default="localhost",
                        help='mqtt host')
    parser.add_argument('--mqttPort', metavar='MQTTPORT', default=1883,
                        help='mqtt port', type=int)
    parser.add_argument('--mysqlLocationUrl', metavar='MYSQLLOCATIONURL', default="https://mysql.parois.net/insertLocation.php",
                        help='myslq location url')
    parser.add_argument('--mysqlStepsUrl', metavar='MYSQLSTEPSURL', default="https://mysql.parois.net/insertSteps.php",
                        help='myslq steps url')
    parser.add_argument('--mysqlUser', metavar='MYSQLUSER', default="grafana",
                        help='myslq user')
    parser.add_argument('--mysqlPassword', metavar='MYSQLPASSWORD',
                        help='myslq password', required=True)
    parser.add_argument('--mysqlDatabase', metavar='MYSQLDATABASE',
                        help='myslq database', default="grafana")
    args = parser.parse_args()

    client = mqtt.Client()
    client.connect(args.mqttHost,args.mqttPort,60)

    client.on_connect = on_connect
    client.on_message = on_message_http

    client.loop_forever()

if __name__ == '__main__':
    try:
        logger.debug("%s starting"%appName)
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
