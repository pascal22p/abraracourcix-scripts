import requests
import json
import logging
import sys
import re
from distutils.version import StrictVersion
import random
import docker
import datetime
import argparse

appName="docker-updates"

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

tagsRe = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+)[^a-zA-Z]+.*")

def getContainersVersion():
    client = docker.from_env()
    containers = client.containers.list()
    imagesList = []
    for container in containers:
        tag = container.image.tags[0].split(":")
        imagesList.append({"name":tag[0], "tag":tag[1]})
    return imagesList

def sendAlert(key, container):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    body = {
        "payload": {
            "summary": "Container %s needs updating"%container,
            "timestamp": timestamp,
            "source": appName,
            "severity": "critical"
        },
        "routing_key": key,
        "dedup_key": "docker-update-%s"%container,
        "event_action": "trigger"
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post("https://events.pagerduty.com/v2/enqueue", headers = headers, data = json.dumps(body))
    if resp.status_code == 202:
        logger.warning("pagerduty alert sent: Container %s needs updating"%container)
    else:
        logger.error("Failed to send pagerduty alert: Container %s needs updating"%container)


def getLatest(image):
    resp = requests.get("https://auth.docker.io/token?service=registry.docker.io&scope=repository:%s:pull"%image)
    if resp.status_code == 401:
        return None
    elif resp.status_code == 200:
        token = resp.json()["token"]
    else:
        logger.error("Failed to get bearer token for %s"%image)

    versions = []
    headers = {"Authorization": "Bearer %s"%token}
    resp = requests.get("https://registry.hub.docker.com/v2/%s/tags/list"%image, headers=headers)
    if resp.status_code == 401:
        return None
    elif resp.status_code == 200:
        tags = resp.json()["tags"]
        for tag in tags:
            match = tagsRe.match(tag)
            if match is not None:
                versions.append(match.group(1))
    else:
        logger.error("Failed to get tags for %s"%image)

    versions.sort(key=StrictVersion)
    return versions[-1]

def main():
    parser = argparse.ArgumentParser(description='Check registry for docker container updates')
    parser.add_argument('--pdkey', metavar='PDKEY', required=True,
                        help='pagerduty routing key')
    args = parser.parse_args()

    for image in getContainersVersion():
        logger.debug("%s is running %s while version %s is available"%(image['name'], image['tag'], getLatest(image['name'])))
        sendAlert(args.pdkey, image['name'])

if __name__ == '__main__':
    main()
