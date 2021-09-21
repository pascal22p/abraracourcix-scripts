#!/bin/bash

while getopts r:c: flag
do
    case "${flag}" in
        r) routing_key=${OPTARG};;
        c) containers=${OPTARG};;
    esac
done

timestamp=`date --rfc-3339=seconds | sed 's/ /T/'`

for container in $containers; do
  if [ "$( docker container inspect -f '{{.State.Status}}' $container )" == "running" ]; then
    action="resolve"

    body=$(cat <<End-of-message
    {
      "payload": {
        "summary": "Docker container $container is not running",
        "timestamp": "$timestamp",
        "source": "abraracourcix.debroglie.net",
        "severity": "critical"
      },
      "routing_key": "$routing_key",
      "dedup_key": "docker-check-$container",
      "event_action": "$action"
    }
End-of-message
    )
  else
    action="trigger"

    body=$(cat <<End-of-message
    {
      "payload": {
        "summary": "Docker container $container is not running",
        "timestamp": "$timestamp",
        "source": "abraracourcix.debroglie.net",
        "severity": "critical"
      },
      "routing_key": "$routing_key",
      "dedup_key": "docker-check-$container",
      "event_action": "$action"
    }
End-of-message
    )
  fi

  curl --location --request POST 'https://events.pagerduty.com/v2/enqueue' --header 'Content-Type: application/json' --data-raw "$body"
  echo ""
done
