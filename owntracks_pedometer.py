#!/usr/bin/env python

import datetime
import time
import json
import sys

days = 0

def unix_epoch(t):
    return int(time.mktime(t.timetuple()))

now = datetime.datetime.today()

f = now.replace(now.year, now.month, now.day, now.hour - 1, 0, 1, 0)
t = now.replace(now.year, now.month, now.day, now.hour - 1, 59, 59, 0)

payload = {
        '_type' : 'cmd',
        'action' : 'reportSteps',
        'from'  : unix_epoch(f),
        'to'    : unix_epoch(t),
}
print(json.dumps(payload))
