import glob
import re
import sys
import os
import logging
import traceback
import sys
import argparse

appName = 'banIps'

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

clientIp = re.compile("client-ip=([0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3})")

subNets = {}

for file in glob.glob('/home/vmail/vhosts/**/.Junk/**', recursive = True):
    if os.path.isfile(file) and "abraracourcix.debroglie.net" in file:
        email = open(file, 'r', encoding='ascii', errors='ignore')
        emailbody = email.read()
        email.close()
        matches = clientIp.findall(emailbody)
        for match in matches:
            subNet = ".".join(match.split(".")[0:-1]) + ".0/24 REDIRECT honeypot@parois.net"
            if subNet not in subNets:
                subNets[subNet] = 1
            else:
                subNets[subNet] += 1

subNets = { key:value for (key,value) in subNets.items() if value > 2}

with open('/etc/postfix/client_checks') as f:
    lines = f.read().strip().splitlines()

toAdd = [ip for ip in list(subNets.keys()) if ip not in lines]
if len(toAdd) > 0:
    logger.info("New Ips to add to blacklist: %s"%toAdd)

    banFile = open("/etc/postfix/client_checks", "a")
    for element in toAdd:
        banFile.write(element + "\n")
    banFile.close()
else:
    logger.info("No new ip to ban")
