#!/usr/bin/env python

import datetime
import time
import json
import sys
import paho.mqtt.client as mqtt
import logging
import traceback
import argparse

appName = 'owntracksRequestSteps'

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


days = 0

def unix_epoch(t):
    return int(time.mktime(t.timetuple()))

def bodyRequest():
    now = datetime.datetime.today()

    f = now.replace(now.year, now.month, now.day, now.hour - 1, 0, 1, 0)
    t = now.replace(now.year, now.month, now.day, now.hour - 1, 59, 59, 0)

    return json.dumps({
            '_type' : 'cmd',
            'action' : 'reportSteps',
            'from'  : unix_epoch(f),
            'to'    : unix_epoch(t),
    })

def on_connect(client, userdata, flags, rc):
    logger.debug("Connected with result code "+str(rc))

def on_publish(client,userdata,result):             #create function for callback
    print("data published \n%s\n%s"%(result, userdata))
    pass

def on_disconnect(client, userdata, rc):
    print("disconnected with rtn code [%d]"% (rc) )

def main():
    global args
    parser = argparse.ArgumentParser(description='subscribe to topics and send data to graphite')
    parser.add_argument('--mqttHost', metavar='MQTTHOST', default="localhost",
                        help='mqtt host')
    parser.add_argument('--mqttPort', metavar='MQTTPORT', default=1883,
                        help='mqtt port', type=int)
    args = parser.parse_args()

    client = mqtt.Client()
    client.connect(args.mqttHost,args.mqttPort,60)

    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect

    (rc, mid) = client.publish("owntracks/user/IphonePascal/cmd",bodyRequest(), qos=2)
    if not rc == mqtt.MQTT_ERR_SUCCESS:
        logger.error('Code %d while sending message %d: %s' %(rc, mid, mqtt.error_string(rc)))
    else:
        logger.debug('Code %d while sending message %d: %s' %(rc, mid, mqtt.error_string(rc)))
    client.disconnect()

if __name__ == '__main__':
    try:
        logger.debug("%s starting"%appName)
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
