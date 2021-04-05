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

appName = "netatmo2graphite"

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

def notNone(x):
    return x is not None

def getLocationCorners(location):
    #Earth’s radius, sphere
    R = 6378137

    #offsets in meters
    dn = 3000
    de = 3000

    #Coordinate offsets in radians
    dLat = dn / R
    dLon = de / (R*math.cos(math.pi * location["lat"]/180.0))

    #OffsetPosition, decimal degrees
    lat_ne = location["lat"] + dLat * 180.0/math.pi
    lon_ne = location["lon"] + dLon * 180.0/math.pi

    lat_sw = location["lat"] - dLat * 180.0/math.pi
    lon_sw = location["lon"] - dLon * 180.0/math.pi

    return {"lat_ne":lat_ne, "lon_ne":lon_ne, "lat_sw":lat_sw, "lon_sw":lon_sw}

class tokenClass:
    token = None
    tokenExpire = None
    refresh = None
    password = None
    client_id = None
    secret_id = None
    username = None
    tokenFile = "/tmp/netatmo2mqtt"

    def __init__(self, config):
        self.token = None
        self.tokenExpire = None
        self.refresh = None
        self.password = config.netatmoPassword
        self.client_id = config.netatmoId
        self.client_secret = config.netatmoSecret
        self.username = config.netatmoUsername

    def __refreshToken(self):
        data = dict(grant_type='refresh_token', refresh_token=self.refresh, client_id=self.client_id, client_secret=self.client_secret)
        resp = requests.post('https://api.netatmo.com/oauth2/token', data=data)
        if resp.status_code == 200:
            token = resp.json()
            self.token = token["access_token"]
            self.tokenExpire = int(time.time()) + token['expires_in']
            self.refresh = token["refresh_token"]

            f = open(self.tokenFile, "w")
            f.write(str(self.tokenExpire) + "\n")
            f.write(self.refresh + "\n")
            f.write(self.token)
            f.close()
            logger.debug("refreshed token %s from netatmo, expires in %d"%(self.token, token['expires_in']))
        else:
            logger.error("Error while refreshing token: %s"%resp.content)
            resp.raise_for_status()

    def __loadFromDisk(self):
        try:
            f = open(self.tokenFile, 'r')
        except FileNotFoundError:
            pass
        else:
            content = f.readlines()
            self.tokenExpire = int(content[0])
            self.refresh = content[1].strip()
            self.token = content[2].strip()
            logger.debug("read token %s from file"%self.token)
            f.close()

    def getToken(self):
        self.__loadFromDisk()
        if self.token is None or (self.tokenExpire < int(time.time())):
            data = dict(grant_type='password', client_id=self.client_id,
                client_secret=self.client_secret, username=self.username,
                password=self.password, scope='read_station')

            resp = requests.post('https://api.netatmo.com/oauth2/token', data=data)
            if resp.status_code == 200:
                token = resp.json()
                self.token = token["access_token"]
                self.tokenExpire = int(time.time()) + token['expires_in']
                self.refresh = token["refresh_token"]
            else:
                logger.error("Error while getting token: %s"%resp.content)
                resp.raise_for_status()

            f = open(self.tokenFile, "w")
            f.write(str(self.tokenExpire) + "\n")
            f.write(self.refresh + "\n")
            f.write(self.token)
            f.close()
            logger.debug("Got new token %s from netatmo, token expires in %d"%(self.token, token['expires_in']))
        else:
            if self.tokenExpire < int(time.time()) + 300:
                # refresh token
                self.__refreshToken()
        return self.token

def getWeatherStationData(token, location):
    corners = getLocationCorners(location)
    url = 'https://api.netatmo.com/api/getpublicdata?access_token=%s&lat_ne=%f&lon_ne=%f&lat_sw=%f&lon_sw=%f'%(
        token, corners["lat_ne"], corners["lon_ne"], corners["lat_sw"], corners["lon_sw"])

    #print(url)
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.json()["body"]
    else:
        resp.raise_for_status()

def getMeasure(name, measure):
    if "type" in measure:
        if name in measure["type"]:
            indexTemp = measure["type"].index(name)
            return list(measure["res"].values())[0][indexTemp]
        else:
            return None
    else:
        if name in measure:
            return measure[name]
        else:
            None

def getAverage(values):
    if len(values) > 11:
        sortedList = numpy.sort(numpy.array(values, dtype=numpy.double))[3:-3]
    else:
        sortedList = numpy.array(values, dtype=numpy.double)
    average = numpy.average(sortedList)
    stdDev = numpy.std(sortedList)
    return average, 2.576 * stdDev / numpy.sqrt(len(values))

def getAngleAverage(values):
    if len(values) > 11:
        sortedList = numpy.sort(numpy.array(values, dtype=numpy.double))[3:-3]
    else:
        sortedList = numpy.array(values, dtype=numpy.double)
    radians = numpy.radians(sortedList)

    sinesSum = numpy.sum(numpy.sin(radians))
    cosinesSum = numpy.sum(numpy.cos(radians))
    stdDev = math.sqrt(-numpy.log(sinesSum ** 2 + cosinesSum ** 2) + numpy.log(len(radians) ** 2))

    return numpy.degrees(math.atan2(sinesSum, cosinesSum)) + 180.0, numpy.degrees(stdDev)


class statsClass:
    def __init__(self):
        self.stats = {}

    def addTo(self, name, value):
        if value is not None:
            if name in self.stats:
                self.stats[name].append(value)
            else:
                self.stats[name] = [value]

    def getList(self, name):
        if name in self.stats:
            return self.stats[name]
        else:
            None

    def getNames(self):
        return self.stats.keys()


def main():
    parser = argparse.ArgumentParser(description='Sent netatmo weather data to mqtt')
    parser.add_argument('--netatmoId', metavar='NETATMOID', required=True,
                        help='Netatmo client id')
    parser.add_argument('--netatmoSecret', metavar='NETATMOSECRET', required=True,
                        help='Netatmo client secret')
    parser.add_argument('--netatmoUsername', metavar='NETATMOUSERNAME', required=True,
                        help='Netatmo username')
    parser.add_argument('--netatmoPassword', metavar='NETATMOPASSWORD', required=True,
                        help='Netatmo password')
    parser.add_argument('--mqttHost', metavar='MQTTHOST', default="localhost",
                        help='mqtt host')
    parser.add_argument('--mqttPort', metavar='MQTTPORT', default=1883,
                        help='mqtt port', type=int)
    args = parser.parse_args()

    mqttClient = mqtt.Client()
    mqttClient.connect(args.mqttHost,args.mqttPort,60)

    token = tokenClass(args)
    location = {"lat": 55.00014637405377, "lon":-1.5854536921597275}

    data = getWeatherStationData(token.getToken(), location)
    #print(data)

    stats = statsClass()
    now = int(time.time())
    for weatherStation in data:
        for measure in list(weatherStation["measures"].values()):
            if "res" in measure and "type" in measure:
                delta = now - int(list(measure["res"].keys())[0])
                if delta < 10 * 60:
                    stats.addTo("temperature", getMeasure("temperature", measure))
                    stats.addTo("pressure", getMeasure("pressure", measure))

            # wind not reliableß
            #windTime = getMeasure("wind_timeutc", measure)
            #if windTime is not None:
                #delta = now - windTime
                #if delta < 10 * 60:
                    #stats.addTo("wind_strength", getMeasure("wind_strength", measure))
                    #stats.addTo("wind_angle", getMeasure("wind_angle", measure))
                    #stats.addTo("gust_strength", getMeasure("gust_strength", measure))
                    #stats.addTo("gust_angle", getMeasure("gust_angle", measure))
                #else:
                    #print(measure)

            rainTime = getMeasure("rain_timeutc", measure)
            if rainTime is not None:
                delta = now - rainTime
                if delta < 10 * 60:
                    stats.addTo("rain_24h", getMeasure("rain_24h", measure))
                    stats.addTo("rain_live", getMeasure("rain_live", measure))
                    stats.addTo("rain_60min", getMeasure("rain_60min", measure))

    mqttBody = {}
    for name in stats.getNames():
        average, confidence = getAverage(stats.getList(name))
        logger.info("got measure %s with average %f and confidence %f"%(name, average, confidence))
        mqttBody["%s_value"%name] = average
        mqttBody["%s_confidence"%name] = confidence
        #print(name, average, confidence)
    mqttClient.publish("homeassistant/netatmo", json.dumps(mqttBody, separators=(',', ':')))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)
