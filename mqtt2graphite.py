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

appName = 'mqtt2graphite'

if False:
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
else:
        logger = logging.getLogger(appName)
        stdout = logging.StreamHandler(sys.stdout)
        logger.addHandler(stdout)
        logger.setLevel(logging.DEBUG)

global Sensors, LastTimeSent, args, args

Prefix = "zigbee2mqtt"
Sensors = ["living-room-sensor1", "stairs-networks", "kitchen-fridge", "kitchen-washing", "kitchen-dryer", "kitchen-dishwasher",
           "metoffice", "noweather", "netatmo", "openweathermap", "KeepAlive", "living-room-socket-tv",
           "kitchen-sensor1", "bedroom-us-sensor1", "upstairs-sensor1", "dining-room-sensor1",
           "bedroom-master-sensor1", "garage-sensor1", "Boiler_CH", "kitchen-kettle"]
errorRegex = re.compile(".*to '([a-zA-Z0-9.-]+)' failed.*")

def graphiteSend(metric, sensor):
    global args
    try:
        conn = socket.create_connection(("localhost", 2003))
        conn.send(("%s\n"%(metric)).encode('utf-8'))
        conn.close()
    except ConnectionError as e:
        logger.error("%s: failed to send %s to graphite with error %s"%(sensor, metric, str(e)))
        pass

def on_connect(client, userdata, flags, rc):
  logger.debug("Connected with result code "+str(rc))
  client.subscribe([("zigbee2mqtt/bridge/logging",0), ("zigbee2mqtt/#",0), ("homeassistant/#",0), ("openweathermap/#",0), ("KeepAlive/#", 0)])

def on_message(client, userdata, msg):
    global args
    logger.debug(msg.payload.decode())
    logger.debug(Sensors)
    logger.debug(msg.topic)
    metric = None
    if msg.topic == "zigbee2mqtt/bridge/logging":
        try:
            payload = json.loads(msg.payload.decode())
        except:
            logger.error("Cannot parse json \"%s\""%msg.payload.decode())
            pass
        else:
            metric = "%s.%s.%s.%s %d"%(args.graphiteKey, Prefix, "logging", payload["level"], 1)
            graphiteSend(metric, "logging/%s"%payload["level"])
            m = errorRegex.search(payload["message"])
            if m:
                metric = "%s.%s.%s.%s %d"%(args.graphiteKey, Prefix, m.group(1), "failure", 1)
                graphiteSend(metric, m.group(1))
            else:
                metric = None
            #    logger.error("Cannot extract sensor \"%s\""%payload["message"])
    else:
        for sensor in Sensors:
            metric = None
            if sensor in msg.topic:
                try:
                    payload = json.loads(msg.payload.decode())
                except:
                    logger.error("Cannot parse json \"%s\""%msg.payload.decode())
                    continue
                for type, value in payload.items():
                    if isinstance(value, str):
                        if value == "ON":
                            metric = "%s.%s.%s %d"%(Prefix, sensor, type, 1)
                        elif value == "OFF":
                            metric = "%s.%s.%s %d"%(Prefix, sensor, type, 0)
                        else:
                            metric = "%s.%s.%s %s"%(Prefix, sensor, type, value)
                    elif isinstance(value, dict):
                        metric = None
                    elif value is not None:
                        try:
                            metric = "%s.%s.%s %f"%(Prefix, sensor, type, value)
                        except TypeError:
                            logger.error("Invalid type: " + "%s.%s.%s %s"%(Prefix, sensor, type, value))
                            metric = None

                    if metric is not None:
                        graphiteSend(metric, sensor)

def main():
    global args
    parser = argparse.ArgumentParser(description='subscribe to topics and send data to graphite')
    parser.add_argument('--graphiteUrl', metavar='GRAPHITEURL', default="localhost",
                        help='graphite host')
    parser.add_argument('--mqttHost', metavar='MQTTHOST', default="localhost",
                        help='mqtt host')
    parser.add_argument('--mqttPort', metavar='MQTTPORT', default=1883,
                        help='mqtt port', type=int)
    args = parser.parse_args()

    client = mqtt.Client()
    client.connect(args.mqttHost,args.mqttPort,60)

    client.on_connect = on_connect
    client.on_message = on_message

    client.loop_forever()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
