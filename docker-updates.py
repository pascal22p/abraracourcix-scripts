import requests
import json
import logging
import sys
import re
from distutils.version import StrictVersion
import random
import docker

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

tagsRe = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+).*")

client = docker.from_env()
containers = client.containers.list()
imagesList = []
for container in containers:
    tag = container.image.tags[0].split(":")
    imagesList.append({"name":tag[0], "tag":tag[1]})

def getLatest(image):
    resp = requests.get("https://auth.docker.io/token?service=registry.docker.io&scope=repository:%s:pull"%image)
    if resp.status_code == 401:
        return None
    elif resp.status_code == 200:
        token = resp.json()["token"]
    else:
        logger.error("Failed to get bearer token for %s"%image)
        resp.raise_for_status()

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
        resp.raise_for_status()

    versions.sort(key=StrictVersion)
    return versions[-1]

for image in imagesList:
    print(image['name'], image['tag'], getLatest(image['name']))
