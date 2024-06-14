#!/bin/bash

while getopts r:c: flag
do
    case "${flag}" in
        r) routing_key=${OPTARG};;
        c) certificates=${OPTARG};;
    esac
done

# 7 days in seconds
DAYS="604800"

# Email settings
_openssl="/usr/bin/openssl"

timestamp=`date --rfc-3339=seconds | sed 's/ /T/'`

for certificate in $certificates; do
  base_name=$(basename ${certificate})
  $_openssl x509 -enddate -noout -in "$certificate"  -checkend "$DAYS" | grep -q 'Certificate will expire'

  if [ $? -eq 0 ]
  then
    action="trigger"

    body=$(cat <<End-of-message
    {
      "payload": {
        "summary": "Certificate $base_name needs to be renewed",
        "timestamp": "$timestamp",
        "source": "$HOSTNAME",
        "severity": "critical"
      },
      "routing_key": "$routing_key",
      "dedup_key": "certificate-check-$base_name",
      "event_action": "$action"
    }
End-of-message
    )
  else
    action="resolve"

    body=$(cat <<End-of-message
    {
      "payload": {
        "summary": "Certificate $certificate needs to be renewed",
        "timestamp": "$timestamp",
        "source": "$HOSTNAME",
        "severity": "critical"
      },
      "routing_key": "$routing_key",
      "dedup_key": "certificate-check-$base_name",
      "event_action": "$action"
    }
End-of-message
    )
  fi

  curl -sS --location --request POST 'https://events.pagerduty.com/v2/enqueue' --header 'Content-Type: application/json' --data-raw "$body"
  echo ""
done
