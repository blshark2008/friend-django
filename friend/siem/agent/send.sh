#!/bin/bash
# send.sh — отправляет JSON-событие на сервер SIEM
# Используется agent.sh: echo "$JSON" | /opt/siem/send.sh

set -u

CONF="/opt/siem/agent.conf"
[ -f "$CONF" ] && source "$CONF"

STATE="/var/lib/siem-agent"
mkdir -p "$STATE"

SERVER="${SIEM_SERVER:-https://127.0.0.1:8000}"
TOKEN="${SIEM_TOKEN:-}"
CURL_TIMEOUT="${CURL_TIMEOUT:-10}"
LOGFILE="$STATE/agent.log"

# Читаем JSON из stdin
PAYLOAD=$(cat)

# Логируем что отправляем
echo "$(date -Iseconds) SEND payload: ${PAYLOAD:0:200}" >> "$LOGFILE"

# Проверяем валидность JSON через python3
if ! echo "$PAYLOAD" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    echo "$(date -Iseconds) ERROR: Invalid JSON payload" >> "$LOGFILE"
    echo "$(date -Iseconds) PAYLOAD: ${PAYLOAD:0:500}" >> "$LOGFILE"
    exit 1
fi

# Отправляем на сервер
RESPONSE=$(curl -s --max-time "$CURL_TIMEOUT" -X POST "${SERVER}/api/siem/ingest/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Token ${TOKEN}" \
    -d "$PAYLOAD" 2>&1)

EXIT_CODE=$?

echo "$(date -Iseconds) SEND response: ${RESPONSE:0:200} (exit=$EXIT_CODE)" >> "$LOGFILE"

exit 0
