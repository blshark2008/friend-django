#!/bin/bash
# Установщик SIEM-агента для Astra Linux.
# Запуск: sudo ./install_agent.sh (из каталога с файлами агента)

set -euo pipefail

# --- Проверка прав ---
if [ "$(id -u)" -ne 0 ]; then
    echo "Запусти от root: sudo ./install_agent.sh" >&2
    exit 1
fi

# --- Проверка наличия всех файлов ---
for f in agent.sh send.sh agent.conf siem-agent-cron; do
    [ -f "$f" ] || { echo "Отсутствует файл: $f" >&2; exit 1; }
done

# --- Зависимости ---
command -v curl >/dev/null 2>&1 || { echo "Не найден curl: apt-get install curl" >&2; exit 1; }

if ! command -v sqlite3 >/dev/null 2>&1; then
    apt-get update -qq
    if apt-get install -y -qq sqlite3 >/dev/null 2>&1; then
        echo "sqlite3 установлен"
    else
        echo "ПРЕДУПРЕЖДЕНИЕ: sqlite3 не установился — история браузеров собираться не будет" >&2
    fi
fi

# --- Установка файлов ---
mkdir -p /opt/siem /var/lib/siem-agent
install -m 750 agent.sh send.sh /opt/siem/
install -m 600 agent.conf /opt/siem/

# --- Проверка конфига ДО первого запуска ---
# shellcheck source=/dev/null
source /opt/siem/agent.conf
if [ -z "${TOKEN:-}" ]; then
    echo "В /opt/siem/agent.conf пустой TOKEN — выпусти его на сервере:" >&2
    echo "  python manage.py drf_create_token <имя_пользователя_агента>" >&2
    exit 1
fi
if [ -z "${SERVER:-}" ]; then
    echo "В /opt/siem/agent.conf пустой SERVER — укажи адрес, например http://10.0.0.5:8000" >&2
    exit 1
fi

# --- Проверка связи с сервером ---
HTTP=$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' "$SERVER" 2>/dev/null)
if [ -n "$HTTP" ]; then
    echo "Сервер доступен (HTTP $HTTP)"
else
    echo "ПРЕДУПРЕЖДЕНИЕ: сервер недоступен ($SERVER) — события будут теряться." >&2
    echo "Проверь адрес, запуск сервера (runserver 0.0.0.0:8000) и файрвол." >&2
fi

# --- Cron: права 0644 и владелец root обязательны, иначе cron проигнорирует файл ---
install -m 644 siem-agent-cron /etc/cron.d/siem-agent

# --- Первичный снимок инвентаризации ---
if /opt/siem/agent.sh inventory; then
    echo "Первичная инвентаризация отправлена"
else
    echo "ПРЕДУПРЕЖДЕНИЕ: первый запуск завершился с ошибкой — смотри /var/lib/siem-agent/agent.log" >&2
fi

echo "Агент установлен."
echo "Токен: $(grep '^TOKEN=' /opt/siem/agent.conf | cut -d= -f2- | cut -c1-8)..."

exit 0
