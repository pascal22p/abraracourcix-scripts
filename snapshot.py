# -*- encoding: utf-8 -*-
'''
First, install the latest release of Python wrapper: $ pip install ovh
'''
import json
import ovh
import time
from datetime import datetime
import logging
import sys
import traceback
import argparse

appName = "snapshot"

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


def waitForOnGoingTask(client, id = None):
    logger.debug("Checking for ongoing tasks...")
    waiting = True
    depth = 0
    start = time.monotonic()
    while waiting:
        waiting = False
        time.sleep(min(120.0, depth * 30.0))
        duration = time.monotonic() - start
        logger.debug("Waited for on going task for %.0f minutes"%(duration / 60.0))
        if duration > 240.0 * 60.0:
            logger.error("Error: task taking more than 4 hours")
            return -1
        elif duration > 120.0 * 60.0:
            logger.warning("Warning: task taking more than 2 hours")
        if id is None:
            tasks = client.get('/vps/***REMOVED***/tasks')
            for task in tasks:
                taskResult = client.get('/vps/***REMOVED***/tasks/%s'%task)
                if taskResult['state']!='done':
                    logger.debug("Waiting for task %s (%s) to finish. progress:%d, state:%s"%(taskResult['type'], taskResult['id'], taskResult['progress'], taskResult['state']))
                    waiting = True
        else:
            taskResult = client.get('/vps/***REMOVED***/tasks/%s'%id)
            if taskResult['state']!='done':
                logger.debug("Waiting for task %s (%s) to finish. progress:%d, state:%s"%(taskResult['type'], taskResult['id'], taskResult['progress'], taskResult['state']))
                waiting = True
        depth += 1
    return 0

def deleteSnapshot(client, depth = 0):
    logger.debug("Deleting existing snapshot...")
    try:
        result = client.delete('/vps/***REMOVED***/snapshot')
        return result['id']
    except ovh.exceptions.ResourceNotFoundError:
        pass
    except:
        time.sleep(30)
        if depth < 2:
            deleteSnapshot(client, depth + 1)
        else:
            raise

def main():
    parser = argparse.ArgumentParser(description='Create a snapshot of the vps')
    parser.add_argument('--endpoint', metavar='ENDPOINT', default="ovh-eu",
                        help='endpoint')
    parser.add_argument('--application_key', metavar='APPKEY', required=True,
                        help='application key')
    parser.add_argument('--application_secret', metavar='APPSECRET', required=True,
                        help='application secret')
    parser.add_argument('--consumer_key', metavar='CONSUMERKEY', required=True,
                        help='consumer key')
    args = parser.parse_args()

    client = ovh.Client(
        endpoint=args.endpoint,
        application_key=args.application_key,
        application_secret=args.application_secret,
        consumer_key=args.consumer_key,
    )

    start = time.monotonic()

    if waitForOnGoingTask(client) == -1:
        logger.error("Cannot create new snapshot, an ongoing task is still running after 4 hours.")
        return

    try:
        result = client.get('/vps/***REMOVED***/snapshot')
    except ovh.exceptions.ResourceNotFoundError:
        deletionNeeded = False
    else:
        id = deleteSnapshot(client)
        waitForOnGoingTask(client, id)

    logger.debug("Creating snapshot...")
    result = client.post('/vps/***REMOVED***/createSnapshot', description='Automated snapshot')
    id = result['id']

    waitForOnGoingTask(client, id)
    duration = time.monotonic() - start
    logger.info("Snapshot created in %.0f minutes"%(duration / 60.0))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
