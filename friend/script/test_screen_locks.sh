#!/bin/bash
# Тест сбора данных о блокировках экрана
# Запуск: bash test_screen_locks.sh

echo "=== Тест сбора данных о блокировках ==="
echo ""

# Проверка journalctl
echo "1. Проверка journalctl (systemd-logind):"
journalctl -u systemd-logind --since="7 days ago" --no-pager 2>/dev/null \
    | grep -iE "Session [0-9]+.*(Locked|Unlocked|locked|unlocked)" \
    | tail -5
echo ""

# Проверка loginctl
echo "2. Проверка loginctl (текущие сессии):"
loginctl list-sessions --no-legend 2>/dev/null
echo ""

# Проверка locked hint для каждой сессии
echo "3. LockedHint для каждой сессии:"
SESSIONS=$(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $1}')
for SID in $SESSIONS; do
    USER=$(loginctl show-session "$SID" -p Name --value 2>/dev/null)
    LOCKED=$(loginctl show-session "$SID" -p LockedHint --value 2>/dev/null)
    STATE=$(loginctl show-session "$SID" -p State --value 2>/dev/null)
    echo "  Session $SID: user=$USER locked=$LOCKED state=$STATE"
done
echo ""

# Проверка агента
echo "4. Проверка работы collect_screen_locks:"
if [ -f /opt/siem/agent.sh ]; then
    echo "  agent.sh найден"
    # Запускаем только функцию collect_screen_locks
    bash -c '
        source /opt/siem/agent.conf 2>/dev/null
        STATE="/var/lib/siem-agent"
        LOGFILE="$STATE/agent.log"
        log() { echo "$(date -Iseconds) $1" >> "$LOGFILE"; }
        HOSTNAME=$(hostname)
        
        # Вставляем функцию collect_screen_locks из agent.sh
        eval "$(sed -n "/^collect_screen_locks()/,/^}/p" /opt/siem/agent.sh)"
        
        collect_screen_locks
    '
    echo "  Последняя запись в логе:"
    tail -3 "$STATE/agent.log" 2>/dev/null
else
    echo "  agent.sh НЕ найден в /opt/siem/"
fi
echo ""

echo "=== Тест завершён ==="
