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
    url = 'https://api.openweathermap.org/data/2.5/onecall?appid=%s&units=metric&lat=%f&lon=%f&exclude=minutely,daily,alerts'%(key, location["lat"], location["lon"])

    #print(url)
    resp = requests.get(url)
    #print(resp)
    if resp.status_code == 200:
        try:
            result = resp.json()
        except:
            logger.error("Invalid json: %s"%(resp.content))
            result = {}
        return result
    else:
        resp.raise_for_status()

def dictfilt(data, excluded):
    return dict([ (i,data[i]) for i in data if i not in set(excluded) ])

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
    #logger.debug("Fetching openweathermap data")

    #location = 3333174
    location = {"lat": 55.00014637405377, "lon":-1.5854536921597275}

    data = getWeatherStationData(args.apiKey, location)
    #print(data)

    excludedKeys = ["sunrise", "sunset", "weather", "dt", "rain", "pop"]

    mqttBodyCurrent = dictfilt(data["current"], excludedKeys)
    mqttBodyCurrent["weather_id"] = data["current"]["weather"][0]["id"]
    mqttBodyHourlyRaw = max(data["hourly"], key=lambda item: item["dt"])
    mqttBodyCurrent["wind_gust_hourly"] = mqttBodyHourlyRaw["wind_gust"]
    if "pop" in  mqttBodyHourlyRaw:
        mqttBodyCurrent["rain_pop"] = mqttBodyHourlyRaw["pop"]
    else:
        mqttBodyCurrent["rain_pop"] = 0
    mqttBodyCurrent["rain_1h"] = 0
    if "rain" in mqttBodyHourlyRaw:
        if "1h" in mqttBodyHourlyRaw["rain"]:
            mqttBodyCurrent["rain_1h"] = mqttBodyHourlyRaw["rain"]["1h"]
    jsonBody = json.dumps(mqttBodyCurrent, separators=(',', ':'))
    logger.info("Sending openweathermap data '%s' to mqtt"%jsonBody)
    #print(jsonBody)
    mqttClient.publish("openweathermap/openweathermap", jsonBody)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
