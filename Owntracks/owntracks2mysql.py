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
import mysql.connector

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

global Users, LastTimeSent, args

Users = ["IphonePascal"]

def insertSteps(mysqlUser, mysqlPassword, database, steps):
    try:
        mydb = mysql.connector.connect(
          host="localhost",
          port=3307,
          user=mysqlUser,
          password=mysqlPassword,
          database=database
        )

        mycursor = mydb.cursor()

        sql = "REPLACE INTO steps (fromDate, toDate, steps, distance, floorsup, floorsdown, user) VALUES (FROM_UNIXTIME(%s), FROM_UNIXTIME(%s), %s, %s, %s, %s, %s)"
        val = (steps['from'], steps['to'], steps['steps'], steps['distance'], steps['floorsup'], steps['floorsdown'], steps['user'])
        mycursor.execute(sql, val)

        mydb.commit()
        mycursor.close()
        mydb.close()
    except Exception as e:
        logging.info('Cannot insert location in database', exc_info=e)
        continue

def insertLocation(mysqlUser, mysqlPassword, database, location):
    try:
        mydb = mysql.connector.connect(
          host="localhost",
          user=mysqlUser,
          password=mysqlPassword,
          database=database
        )

        mycursor = mydb.cursor()

        sql = "REPLACE INTO locations (acc, alt, lat, lon, tid, tst, vac, vel, p, user) VALUES (%s, %s, %s, %s, %s, FROM_UNIXTIME(%s), %s, %s, %s, %s)"
        val = (location['acc'], location['alt'], location['lat'], location['lon'], location['tid'], location['tst'], location['vac'], location['vel'], location['p'], location['user'])
        mycursor.execute(sql, val)

        mydb.commit()
        mycursor.close()
        mydb.close()
    except Exception as e:
        logging.info('Cannot insert location in database', exc_info=e)
        continue

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
                payload["user"]=user
            except:
                logger.error("Cannot parse json \"%s\""%msg.payload.decode())
                continue
            if (payload["_type"].lower() == "location"):
                insertLocation(args.mysqlUser, args.mysqlPassword, args.mysqlDatabase, payload)
            elif (payload["_type"].lower() == "steps"):
                insertSteps(args.mysqlUser, args.mysqlPassword, args.mysqlDatabase, payload)
            else:
                logger.info(json.dumps(payload, separators=(',', ':')))

def main():
    global args
    parser = argparse.ArgumentParser(description='subscribe to topics and send data to graphite')
    parser.add_argument('--mqttHost', metavar='MQTTHOST', default="localhost",
                        help='mqtt host')
    parser.add_argument('--mqttPort', metavar='MQTTPORT', default=1883,
                        help='mqtt port', type=int)
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
        logger.error('An unexpected error occurred' + "".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        pass
