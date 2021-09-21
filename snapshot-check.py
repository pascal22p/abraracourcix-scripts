# -*- encoding: utf-8 -*-
import json
import ovh
import time
from datetime import datetime, timezone
import logging
import sys
import traceback
import argparse

appName = "snapshot-check"

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
    parser.add_argument('--vps', metavar='VPSNAME', required=True,
                        help='vps name')
    args = parser.parse_args()

    client = ovh.Client(
        endpoint=args.endpoint,
        application_key=args.application_key,
        application_secret=args.application_secret,
        consumer_key=args.consumer_key,
    )

    try:
        result = client.get('/vps/%s/snapshot'%args.name)
    except ovh.exceptions.ResourceNotFoundError:
        logger.error("vps snapshot cannot be found")
    else:
        snapshotDate = datetime.strptime(result['creationDate'], '%Y-%m-%dT%H:%M:%S%z')
        logger.debug(snapshotDate)
        oldDays = (datetime.now(timezone.utc) - snapshotDate).days
        if oldDays <= 1:
            logger.info("vps snapshot is %d days old"%oldDays)
        elif oldDays <=2:
            logger.warning("vps snapshot is %d days old"%oldDays)
        else:
            logger.error("vps snapshot is %d days old"%oldDays)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
