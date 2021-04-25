import requests
import time
import math
import numpy
import os
import datetime
import logging
import sys
import traceback
import argparse
import json
import paho.mqtt.client as mqtt

appName = "openweathermap2graphite"

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

def getLastValue():
    lastValue = -1
    try:
        f = open("/tmp/openweathermap.lastvalue", 'r')
    except FileNotFoundError:
        pass
    else:
        try:
            lastValue = int(f.read())
        except ValueError:
            lastValue = -1
        f.close()
    return lastValue

def updateLastValue(timestamp):
    f = open("/tmp/openweathermap.lastvalue", 'w')
    f.write("%d"%timestamp)
    f.close()

def getWeatherStationData(key, location):
    url = 'https://api.openweathermap.org/data/2.5/weather?appid=%s&id=%d&units=metric'%(key, location)

    #print(url)
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.json()
    else:
        resp.raise_for_status()

def main():
    parser = argparse.ArgumentParser(description='Sent openweathermap data to mqtt')
    parser.add_argument('--apiKey', metavar='APIKEY', required=True,
                        help='openweathermap client key')
    parser.add_argument('--mqttHost', metavar='MQTTHOST', default="localhost",
                        help='mqtt host')
    parser.add_argument('--mqttPort', metavar='MQTTPORT', default=1883,
                        help='mqtt port', type=int)
    args = parser.parse_args()

    mqttClient = mqtt.Client()
    mqttClient.connect(args.mqttHost,args.mqttPort,60)

    location = 3333174

    data = getWeatherStationData(args.apiKey, location)
    #print(data)

    mqttBody = data["main"]
    mqttBody["visibility"] = data["visibility"]
    if "wind" in data:
        if "speed" in data["wind"]:
            mqttBody["wind_speed"] = data["wind"]["speed"]
        if "gust" in data["wind"]:
            mqttBody["wind_gust"] = data["wind"]["gust"]
        if "deg" in data["wind"]:
            mqttBody["wind_deg"] = data["wind"]["deg"]
    if "rain" in data:
        if "1h" in data["rain"]:
            mqttBody["rain_1h"] = data["rain"]["1h"]
        if "3h" in data["rain"]:
            mqttBody["rain_3h"] = data["rain"]["3h"]
    if "snow" in data:
        if "1h" in data["snow"]:
            mqttBody["snow_1h"] = data["snow"]["1h"]
        if "3h" in data["rain"]:
            mqttBody["snow_3h"] = data["snow"]["3h"]
    if "clouds" in data:
        if "all" in data["clouds"]:
            mqttBody["clouds_all"] = data["clouds"]["all"]
    #print(mqttBody)

    timestamp = data["dt"]
    lastValue = getLastValue()
    if ( timestamp > lastValue + 60):
        jsonBody = json.dumps(mqttBody, separators=(',', ':'))
        logger.info("Sending openweathermap data '%s' to mqtt"%jsonBody)
        mqttClient.publish("openweathermap/openweathermap", jsonBody)
        updateLastValue(timestamp)
    else:
        logger.info('Nothing new to send')

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
