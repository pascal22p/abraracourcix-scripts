#!/usr/bin/env python3

import json
import time
from datetime import datetime
import logging
import traceback
import sys
import argparse
import requests
from requests.auth import HTTPBasicAuth
import re

appName = 'GoogleNest'

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

def refresh_token(client_id, client_secret, refresh_token):
    url = "https://www.googleapis.com/oauth2/v4/token?client_id=%s&client_secret=%s&refresh_token=%s&grant_type=refresh_token"%(client_id, client_secret, refresh_token)
    response = requests.post(
        url = url)
    try:
        data = response.json()
    except:
        logger.error("Cannot read %s. Response status is %d"%(response.text(), response.status_code))
        pass
    else:
        return data["access_token"]

def get_nest_data(project_id, device_id, bearer_token):
    url = "https://smartdevicemanagement.googleapis.com/v1/enterprises/%s/devices/%s"%(project_id, device_id)
    headers = {"Authorization": "Bearer %s"%(bearer_token)}
    response = requests.get(
        url = url,
        headers= headers)
    try:
        data = response.json()
    except:
        logger.error("Cannot read %s. Response status is %d"%(response.text(), response.status_code))
        pass
    else:
        return data

def graphiteHttpPost(graphiteUrl, metric):
    try:
        resp = requests.post(
            graphiteUrl,
            data=metric.encode())
    except ConnectionError as e:
        logger.error("%s: failed to send energy consumption to graphite with error %s"%(metric, str(e)))
        pass
    else:
        if resp.status_code == 202 or resp.status_code == 200:
            logger.info("sent metrics to graphite")
        else:
            logger.error("failed to send metrics to graphite with response %s (%d)"%(resp.text, resp.status_code))

def main():
    parser = argparse.ArgumentParser(description='Push Google nest metrics to graphite')
    parser.add_argument('--graphiteKey', metavar='GRAPHITEKEY', required=True,
                        help='graphite key')
    parser.add_argument('--graphiteUrl', metavar='GRAPHITEURL', default="https://graphite.debroglie.net/graphiteSink.php",
                        help='graphite host')
    parser.add_argument('--clientId', metavar='CLIENT_ID', required=True,
                        help='google API client id')
    parser.add_argument('--clientSecret', metavar='CLIENT_SECRET', required=True,
                        help='google API client secret')
    parser.add_argument('--refreshToken', metavar='REFRESH_TOKEN', required=True,
                        help='google API refresh token')
    parser.add_argument('--projectId', metavar='PROJECT_ID', required=True,
                        help='google API project id')
    parser.add_argument('--deviceId', metavar='DEVICE_ID', required=True,
                        help='google API device id')
    args = parser.parse_args()

    bearer_token = refresh_token(args.clientId, args.clientSecret, args.refreshToken)
    data = get_nest_data(args.projectId, args.deviceId, bearer_token)

    humidity = data["traits"]["sdm.devices.traits.Humidity"]["ambientHumidityPercent"]
    temperature = data["traits"]["sdm.devices.traits.Temperature"]["ambientTemperatureCelsius"]
    if "heatCelsius" in data["traits"]["sdm.devices.traits.ThermostatTemperatureSetpoint"]:
        target = data["traits"]["sdm.devices.traits.ThermostatTemperatureSetpoint"]["heatCelsius"]
    else:
        target = None
    if "status" in data["traits"]["sdm.devices.traits.ThermostatHvac"]:
        if data["traits"]["sdm.devices.traits.ThermostatHvac"]["status"] == "HEATING":
            status = 1
        else:
            status = 0
    else:
        status = None

    timestamp = time.time()

    metrics = "%s.%s %f %d"%(args.graphiteKey, "google-nest.temperature", temperature, timestamp)
    metrics += "\n"
    metrics += "%s.%s %f %d"%(args.graphiteKey, "google-nest.humidity", humidity, timestamp)
    metrics += "\n"
    if target is not None:
        metrics += "%s.%s %f %d"%(args.graphiteKey, "google-nest.target-temperature", target, timestamp)
        metrics += "\n"
    if status is not None:
        metrics += "%s.%s %f %d"%(args.graphiteKey, "google-nest.status", status, timestamp)
        metrics += "\n"
    graphiteHttpPost(args.graphiteUrl, metrics)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
