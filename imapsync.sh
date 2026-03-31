#!/bin/bash
set -o pipefail

LOG_TAG="imapsync"
MAILBOX="INBOX"

usage() {
  echo "Usage: $0 -d dbname [-u dbuser] [-p dbpass] [-q query] \
    --host1 host --port1 port \
    --host2 host --port2 port \
    --api-host host --api-port port --api-key key \
    [--mailbox mailbox]"
  exit 1
}

log() {
  local PRIORITY="${1}"
  local MESSAGE="${2}"
  echo "${MESSAGE}"
  echo "${MESSAGE}" | systemd-cat -t "${LOG_TAG}" -p "${PRIORITY}"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--database) DB_NAME="$2"; shift 2 ;;
    -u|--dbuser)   DB_USER="$2"; shift 2 ;;
    -p|--dbpass)   DB_PASS="$2"; shift 2 ;;
    -q|--query)    SQL_QUERY="$2"; shift 2 ;;
    --host1)       HOST1="$2"; shift 2 ;;
    --port1)       PORT1="$2"; shift 2 ;;
    --host2)       HOST2="$2"; shift 2 ;;
    --port2)       PORT2="$2"; shift 2 ;;
    --api-host)    API_HOST="$2"; shift 2 ;;
    --api-port)    API_PORT="$2"; shift 2 ;;
    --api-key)     API_KEY="$2"; shift 2 ;;
    --mailbox)     MAILBOX="$2"; shift 2 ;;
    *) usage ;;
  esac
done

# Validate required params
[ -z "$DB_NAME" ]  && usage
[ -z "$HOST1" ]    && usage
[ -z "$PORT1" ]    && usage
[ -z "$HOST2" ]    && usage
[ -z "$PORT2" ]    && usage
[ -z "$API_HOST" ] && usage
[ -z "$API_PORT" ] && usage
[ -z "$API_KEY" ]  && usage

# Default SQL query
SQL_QUERY=${SQL_QUERY:-"SELECT username FROM mailbox WHERE active = '1';"}

# Build mysql command
MYSQL_CMD="mysql -sN"
[ -n "$DB_USER" ] && MYSQL_CMD="$MYSQL_CMD -u$DB_USER"
[ -n "$DB_PASS" ] && MYSQL_CMD="$MYSQL_CMD -p$DB_PASS"
MYSQL_CMD="$MYSQL_CMD -D $DB_NAME -e \"$SQL_QUERY\""

# Compare message counts between API and local doveadm
compare_messages() {
  local USER="${1}"
  local API_URL="http://${API_HOST}:${API_PORT}/doveadm/v1"
  local AUTH_HEADER="Authorization: X-Dovecot-API $(echo -n "${API_KEY}" | base64)"

  local API_COUNT
  API_COUNT=$(curl -s \
    -H "${AUTH_HEADER}" \
    -H "Content-Type: application/json" \
    -X POST "${API_URL}" \
    -d "[[\"mailboxStatus\", {\"user\": \"${USER}\", \"mailboxMask\": [\"${MAILBOX}\"], \"field\": [\"messages\"]}, \"t1\"]]" \
    | jq -r '.[0][1][0].messages')

  if [[ -z "${API_COUNT}" || "${API_COUNT}" == "null" ]]; then
    log err "[$USER] Failed to get message count from HTTP API (${API_URL})"
    return 1
  fi

  local LOCAL_COUNT
  LOCAL_COUNT=$(doveadm mailbox status -u "${USER}" messages "${MAILBOX}" \
    | awk '{print $2}')

  if [[ -z "${LOCAL_COUNT}" ]]; then
    log err "[$USER] Failed to get message count from local doveadm"
    return 1
  fi

  log info "[$USER] ${MAILBOX} — API: ${API_COUNT} | Local: ${LOCAL_COUNT}"

  if [[ "${API_COUNT}" == "${LOCAL_COUNT}" ]]; then
    log info "[$USER] MATCH (${API_COUNT} messages)"
  else
    log warning "[$USER] MISMATCH — API=${API_COUNT} local=${LOCAL_COUNT} diff=$((API_COUNT - LOCAL_COUNT))"
  fi
}

# Fetch users
USERS=$(eval $MYSQL_CMD)

EXIT_AUTH_FAILURE=162
RETRY_DELAY=1

run_imapsync() {
  local USER="${1}"
  local TMPLOG
  TMPLOG=$(mktemp)

  imapsync \
    --host1 "$HOST1" --port1 "$PORT1" --user1 "$USER" --password1 x \
    --host2 "$HOST2" --port2 "$PORT2" --user2 "$USER" --password2 x \
    --notls1 --notls2 \
    --syncinternaldates --useuid --noexpungeaftereach \
    --nofoldersizes --delete2 --delete2folders \
    >"$TMPLOG" 2>&1
  local EXIT_CODE=$?

  cat "$TMPLOG" | systemd-cat -t $LOG_TAG
  rm -f "$TMPLOG"
  return $EXIT_CODE
}

# Loop users
for USER in $USERS; do
  log info "[$USER] Starting sync"

  run_imapsync "$USER"
  EXIT_CODE=$?

  if [ $EXIT_CODE -eq $EXIT_AUTH_FAILURE ]; then
    log warning "[$USER] Auth failure (162) — retrying in ${RETRY_DELAY}s"
    sleep $RETRY_DELAY
    run_imapsync "$USER"
    EXIT_CODE=$?
  fi

  if [ $EXIT_CODE -eq 0 ]; then
    log info "[$USER] Sync SUCCESS"
    compare_messages "$USER"
  else
    log err "[$USER] Sync ERROR (exit code: $EXIT_CODE) — skipping message count comparison"
  fi

  sleep 1
done

