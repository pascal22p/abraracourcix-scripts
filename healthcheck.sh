#!/usr/bin/env bash

/usr/bin/mosquitto_pub -t zigbee2mqtt/garage-socket1/get -m '{"state":""}' 
/usr/bin/mosquitto_pub -t zigbee2mqtt/garage-socket2/get -m '{"state":""}'
/usr/bin/mosquitto_pub -t zigbee2mqtt/kitchen-socket1/get -m '{"state":""}'
/usr/bin/mosquitto_pub -t zigbee2mqtt/kitchen-socket2/get -m '{"state":""}'
/usr/bin/mosquitto_pub -t zigbee2mqtt/office-socket1/get -m '{"state":""}'
/usr/bin/mosquitto_pub -t zigbee2mqtt/living-room-socket-tv/get -m '{"state":""}'

