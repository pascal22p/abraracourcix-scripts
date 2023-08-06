#!/usr/bin/env bash

/usr/bin/mosquitto_pub -t zigbee2mqtt/kitchen-fridge/get -m '{"state":""}' 
/usr/bin/mosquitto_pub -t zigbee2mqtt/kitchen-washing/get -m '{"state":""}'
/usr/bin/mosquitto_pub -t zigbee2mqtt/kitchen-dryer/get -m '{"state":""}'
/usr/bin/mosquitto_pub -t zigbee2mqtt/stairs-network/get -m '{"state":""}'
/usr/bin/mosquitto_pub -t zigbee2mqtt/living-room-socket-tv/get -m '{"state":""}'
/usr/bin/mosquitto_pub -t zigbee2mqtt/kitchen-kettle/get -m '{"state":""}'
