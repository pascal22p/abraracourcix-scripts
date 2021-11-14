#!/usr/bin/python

import requests
import logging
import traceback
import sys
import argparse
from dateutil import parser as dateParse

appName = 'OctopusEnergy'

if True:
    logger = logging.getLogger(appName)
    stdout = logging.StreamHandler(sys.stdout)
    logger.addHandler(stdout)
    logger.setLevel(logging.DEBUG)
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

def getGasComsumptionInKwh(API_KEY, mprn, gasMeter, days = 1):
    pageSize = 24 * 2 * (days + 1)
    url = "https://api.octopus.energy/v1/gas-meter-points/%s/meters/%s/consumption/?page_size=%d"%(mprn, gasMeter, pageSize)
    response = requests.get(
        url = url,
        auth=(API_KEY, ""))
    try:
        data = response.json()
    except:
        logger.error("Cannot read %s. Response status is %d"%(response.text(), response.status_code))
        pass
    else:
        return data["results"]

def getElectricityComsumptionInKwh(API_KEY, mpan, electricMeter, days = 1):
    pageSize = 24 * 2 * (days + 1)
    url = "https://api.octopus.energy/v1/electricity-meter-points/%s/meters/%s/consumption/?page_size=%d"%(mpan, electricMeter, pageSize)
    response = requests.get(
        url = url,
        auth=(API_KEY, ""))
    try:
        data = response.json()
    except:
        logger.error("Cannot read %s. Response status is %d"%(response.text(), response.status_code))
        pass
    else:
        return data["results"]
    return None


def main():
    global args, token
    parser = argparse.ArgumentParser(description='Gather data from Octopus API and send it to graphite')
    parser.add_argument('--graphiteKey', metavar='GRAPHITEKEY', required=True,
                        help='graphite key')
    parser.add_argument('--graphiteUrl', metavar='GRAPHITEURL', default="https://graphite.debroglie.net/graphiteSink.php",
                        help='graphite host')
    parser.add_argument('--apiKey', metavar='APIKEY', required=True,
                        help='octopus api key')
    parser.add_argument('--mpan', metavar='MPAN', required=True,
                        help='MPAN')
    parser.add_argument('--eSerial', metavar='ESERIAL', required=True,
                        help='electric meter serial number')
    parser.add_argument('--mprn', metavar='MPRN', required=True,
                        help='MPRN')
    parser.add_argument('--gSerial', metavar='GSERIAL', required=True,
                        help='gas meter serial number')
    parser.add_argument('--days', metavar='DAYS', default=1,
                        help='nuber of days to fetch')
    args = parser.parse_args()

    gasData = getGasComsumptionInKwh(args.apiKey, args.mprn, args.gSerial,args.days)
    if gasData:
        metrics = ""
        for measure in gasData:
            if measure["consumption"] > 0:
                metric = "%s.%s %f %d"%(args.graphiteKey, "energy.gas.consumption", measure["consumption"], dateParse.parse(measure["interval_end"]).timestamp())
                metrics += metric + "\n"
        if metrics:
            graphiteHttpPost(args.graphiteUrl, metrics)

    metrics = ""
    elecData = getElectricityComsumptionInKwh(args.apiKey, args.mpan, args.eSerial,args.days)
    if elecData:
        for measure in elecData:
            if measure["consumption"] > 0:
                metric = "%s.%s %f %d"%(args.graphiteKey, "energy.electricity.consumption", measure["consumption"], dateParse.parse(measure["interval_end"]).timestamp())
                metrics += metric + "\n"
        if metrics:
            graphiteHttpPost(args.graphiteUrl, metrics)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        pass
