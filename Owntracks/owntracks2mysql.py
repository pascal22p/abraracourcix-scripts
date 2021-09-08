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

global Users, LastTimeSent, args, args

Users = ["IphonePascal"]

def sendLocation(payload, mysqlHost, mysqlUser, mysqlPassword):
    if 'vel' in payload:
        vel = payload['vel']
    else:
        vel = None

    try:
        connection = mysql.connector.connect(host=mysqlHost,
                                         database='grafana',
                                         user=mysqlUser,
                                         password=mysqlPassword)

        mySql_insert_query = """INSERT IGNORE INTO locations (`acc`, `alt`, `lat`, `lon`, `tid`, `tst`, `vac`, `vel`, `p`)
                                VALUES
                                (%d, %d, %f, %f, '%s', %d, %d, %d, %f) """%(
                                payload['acc'], payload['alt'], payload['lat'], payload['lon'], payload['tid'], payload['tst'], payload['vac'], payload['vel'], payload['p'])
        logger.debug(mySql_insert_query)
        cursor = connection.cursor()
        cursor.execute(mySql_insert_query)
        connection.commit()
        logger.info("%d Record inserted successfully into Laptop table"%cursor.rowcount)
        cursor.close()

    except mysql.connector.Error as error:
        logger.error("Failed to insert record into Laptop table {}".format(error))
    finally:
        if connection.is_connected():
            connection.close()
            logger.debug("MySQL connection is closed")

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
                sendLocation(payload, args.mysqlHost, args.mysqlUser, args.mysqlPassword)
            elif (payload["_type"].lower() == "steps"):
                sendSteps(payload)

def main():
    global args
    parser = argparse.ArgumentParser(description='subscribe to topics and send data to graphite')
    parser.add_argument('--mqttHost', metavar='MQTTHOST', default="localhost",
                        help='mqtt host')
    parser.add_argument('--mqttPort', metavar='MQTTPORT', default=8883,
                        help='mqtt port', type=int)
    parser.add_argument('--mqttCert', metavar='MQTTCERT',
                        help='mqtt client certificate', required=True)
    parser.add_argument('--mysqlHost', metavar='MYSQLHOST', default="localhost",
                        help='myslq host')
    parser.add_argument('--mysqlUser', metavar='MYSQLUSER', default="grafana",
                        help='myslq user')
    parser.add_argument('--mysqlPassword', metavar='MYSQLPASSWORD',
                        help='myslq password', required=True)
    args = parser.parse_args()

    client = mqtt.Client()
    client.tls_set(certfile=args.mqttCert)
    client.tls_insecure_set(True)
    print("here")
    f = client.connect(args.mqttHost,args.mqttPort,60)
    print("done?")
    print(f)

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
