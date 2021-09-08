#!/bin/bash
routing_key=$1
lookAt=$2
timestamp=`date --rfc-3339=seconds | sed 's/ /T/'`
source=`hostname`

for service in $lookAt; do
    result=`systemctl is-active $service`
    if [[ $result != "active" ]]; then
      systemd-cat -t service-check -p err echo "$service is not running"
      action="trigger"
      body=$(cat <<End-of-message
      {
        "payload": {
          "summary": "Service $service is not running",
          "timestamp": "$timestamp",
          "source": "$source",
          "severity": "critical"
        },
        "routing_key": "$routing_key",
        "dedup_key": "service-check-$service",
        "event_action": "$action"
      }
End-of-message
      )
    else
      action="resolve"
      body=$(cat <<End-of-message
      {
        "payload": {
          "summary": "Service $service is not running",
          "timestamp": "$timestamp",
          "source": "$source",
          "severity": "critical"
        },
        "routing_key": "$routing_key",
        "dedup_key": "service-check-$service",
        "event_action": "$action"
      }
End-of-message
      )
    fi

    curl --silent --location --request POST 'https://events.pagerduty.com/v2/enqueue' --header 'Content-Type: application/json' --data-raw "$body"
    echo ""
done

