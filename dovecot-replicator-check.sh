#!/bin/bash
routing_key=$1
lookAt=$2
timestamp=`date --rfc-3339=seconds | sed 's/ /T/'`
source=`hostname`

result=`doveadm replicator status '*' | grep " y "`

    if [[ -n "$result" ]]; then
      action="trigger"
      body=$(cat <<End-of-message
      {
        "payload": {
          "summary": "Mail replication is broken",
          "timestamp": "$timestamp",
          "source": "$source",
          "severity": "critical"
        },
        "routing_key": "$routing_key",
        "dedup_key": "mail-replicator",
        "event_action": "$action"
      }
End-of-message
      )
    else
      action="resolve"
      body=$(cat <<End-of-message
      {
        "payload": {
          "summary": "Mail replication is running",
          "timestamp": "$timestamp",
          "source": "$source",
          "severity": "critical"
        },
        "routing_key": "$routing_key",
        "dedup_key": "mail-replicator",
        "event_action": "$action"
      }
End-of-message
      )
    fi

    curl --silent --location --request POST 'https://events.pagerduty.com/v2/enqueue' --header 'Content-Type: application/json' --data-raw "$body"
    echo ""

