#!/bin/bash
lookAt=$1
for service in $lookAt; do
    result=`systemctl is-active $service`
    if [[ $result != "active" ]]; then
        systemd-cat -t service-check -p err echo "$service is not running"
    fi
done

