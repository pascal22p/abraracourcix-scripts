import mysql.connector as mysql
import argparse
import logging
import json
import requests
import sys
import datetime

appName = 'mariadb_replication_check'

if False:
    try:
        from systemd.journal import JournalHandler
        logger = logging.getLogger(appName)
        logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER=appName))
    except ImportError:
        logger = logging.getLogger(appName)
        stdout = logging.StreamHandler(sys.stdout)
        logger.addHandler(stdout)
    finally:
        logger.setLevel(logging.INFO)
else:
    logger = logging.getLogger(appName)
    stdout = logging.StreamHandler(sys.stdout)
    logger.addHandler(stdout)
    logger.setLevel(logging.DEBUG)

SLAVE_IO_RUNNING = 10
SLAVE_SQL_RUNNING = 11
SECONDS_BEHIND_MASTER = 32

def sendAlert(key, description, status):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    body = {
        "payload": {
            "summary": "Mariadb replica is not working correctly",
            "timestamp": timestamp,
            "source": appName,
            "severity": "critical",
            "custom_details": {
                "description": description
            }
        },
        "routing_key": key,
        "dedup_key": "mariadb-deplica-check",
        "event_action": status
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post("https://events.pagerduty.com/v2/enqueue", headers = headers, data = json.dumps(body))
    if resp.status_code == 202:
        #logger.warning("pagerduty alert sent: Container %s needs updating"%container)
        pass
    else:
        logger.error("Failed to send pagerduty alert: Container %s needs updating"%container)


parser = argparse.ArgumentParser(description='Check mariadb slave status')
parser.add_argument('--host', metavar='HOST', default="127.0.0.1",
                    help='host')
parser.add_argument('--user', metavar='USER', required=True,
                    help='user')
parser.add_argument('--password', metavar='PASSWORD', required=True,
                    help='password')
parser.add_argument('--port', metavar='PORT', type=int, default=3306,
                    help='port')
parser.add_argument('--pdkey', metavar='PDKEY', required=True,
                    help='pagerduty routing key')
args = parser.parse_args()


db = mysql.connect(
    host = args.host,
    user = args.user,
    passwd = args.password,
    database = "INFORMATION_SCHEMA"
)

cursor = db.cursor()

try:
    query = "SHOW REPLICA STATUS"
    cursor.execute(query)
    records = cursor.fetchall()
except Exception as e:
   description = str(e)
   sendAlert(args.pdkey, description, "trigger")
else:
    record = records[0]
    names = cursor.description

    description = "Replication is not working the way it should be:\n"
    description += "%s: %s\n"%(names[SLAVE_IO_RUNNING][0], record[SLAVE_IO_RUNNING])
    description += "%s: %s\n"%(names[SLAVE_SQL_RUNNING][0], record[SLAVE_SQL_RUNNING])
    description += "%s: %s\n"%(names[SECONDS_BEHIND_MASTER][0], record[SECONDS_BEHIND_MASTER])

    if record[SLAVE_IO_RUNNING] != "Yes" or record[SLAVE_SQL_RUNNING] != "Yes" or int(record[SECONDS_BEHIND_MASTER])>60:
        logger.error("Alert triggered:\n" + description)
        sendAlert(args.pdkey, description, "trigger")
    else:
        logger.debug("replication status (debug): \n" + description)
        sendAlert(args.pdkey, description, "resolve")
