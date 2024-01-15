#!/usr/bin/env python

import datetime
import time
import json
import sys
import paho.mqtt.publish as publish
import logging
import traceback
import argparse
from datetime import timezone

appName = 'owntracksRequestSteps'

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
        logger.setLevel(logging.DEBUG)
else:
        logger = logging.getLogger(appName)
        stdout = logging.StreamHandler(sys.stdout)
        logger.addHandler(stdout)
        logger.setLevel(logging.DEBUG)

def unix_epoch(t):
    return int(time.mktime(t.timetuple()))

def bodyRequest(offset):
    now = datetime.datetime.today()

    f = now.replace(now.year, now.month, now.day, now.hour, 0, 0, 0) - datetime.timedelta(hours=offset)
    t = now.replace(now.year, now.month, now.day, now.hour, 59, 59, 0) - datetime.timedelta(hours=offset)

    return json.dumps({
            '_type' : 'cmd',
            'action' : 'reportSteps',
            'from'  : unix_epoch(f),
            'to'    : unix_epoch(t),
    })

def main():
    global args
    parser = argparse.ArgumentParser(description='subscribe to topics and send data to graphite')
    parser.add_argument('--mqttHost', metavar='MQTTHOST', default="localhost",
                        help='mqtt host')
    parser.add_argument('--mqttPort', metavar='MQTTPORT', default=1883,
                        help='mqtt port', type=int)
    parser.add_argument('--device', metavar='DEVICE', required=True, action='append',
                        help='owntracks device name')
    parser.add_argument('--duration', metavar='MQTTPORT', default=4,
                        help='number of hours to query', type=int)
    args = parser.parse_args()

    devices = args.device

    for i in range(0, args.duration):
        time.sleep(0.5)
        for device in devices:
            result = publish.single("owntracks/user/%s/cmd"%device, payload=bodyRequest(i), qos=2, hostname=args.mqttHost, port=args.mqttPort)
            print("owntracks/user/%s/cmd"%device, result)

if __name__ == '__main__':
    try:
        logger.debug("%s starting"%appName)
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
