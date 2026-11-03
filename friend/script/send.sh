#!/bin/bash
# Отправляет JSON на сервер. Вход: JSON через stdin.
# Проблемы с сетью НЕ ломают работу агента: просто пишем в локальный лог.

SERVER="$(grep '^SERVER=' /opt/siem/agent.conf | cut -d= -f2- | tr -d '"')"
TOKEN="$(grep '^TOKEN=' /opt/siem/agent.conf | cut -d= -f2- | tr -d '"')"
CURL_TIMEOUT="$(grep '^CURL_TIMEOUT=' /opt/siem/agent.conf | cut -d= -f2- | tr -d '"')"
CURL_TIMEOUT="${CURL_TIMEOUT:-10}"

LOGFILE="/var/lib/siem-agent/agent.log"

RESPONSE=$(curl -s --max-time "$CURL_TIMEOUT" \
    -X POST "$SERVER/api/siem/ingest/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Token $TOKEN" \
    -d @- 2>>"$LOGFILE")   # читает JSON из stdin

RC=$?
if [ $RC -ne 0 ]; then
    echo "$(date -Iseconds) curl exit=$RC — сервер недоступен" >> "$LOGFILE"
    # Если не удалось отправить — записываем в лог локально,
    # чтобы потом можно было вручную изучить.
fi
