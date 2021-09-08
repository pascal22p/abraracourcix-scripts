#!/usr/bin/env bash

/usr/bin/mosquitto_pub -t zigbee2mqtt/garage-socket1/get -m '{"state":""}' 
/usr/bin/mosquitto_pub -t zigbee2mqtt/kitchen-socket1/get -m '{"state":""}'
/usr/bin/mosquitto_pub -t KeepAlive -m '{"mosquitto":1}' 

