#!/bin/bash
# ============================================================================
# Мониторинг SSH reverse tunnel с автовосстановлением
# ============================================================================
# Запуск:
#   bash deploy/monitor_tunnel.sh
#
# Скрипт проверяет туннель каждые 30 секунд и переподключается при обрыве.
# ============================================================================

SSH_USER="pechea"
SSH_HOST="84.54.59.213"
SSH_KEY="$HOME/.ssh/id_ed25519"
SSH_PORT=22
REMOTE_PORT=8000
LOG_FILE="/tmp/tunnel_monitor.log"

echo "============================================"
echo "  Tunnel Monitor (автовосстановление)"
echo "============================================"
echo ""
echo "  Сервер:   $SSH_HOST"
echo "  Локально: localhost:$REMOTE_PORT"
echo "  Проверка: каждые 30 секунд"
echo "  Лог:      $LOG_FILE"
echo ""

# Функция логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Функция проверки туннеля
check_tunnel() {
    # Проверяем, запущен ли туннель
    TUNNEL_PID=$(pgrep -f "ssh.*-R.*$REMOTE_PORT.*$SSH_HOST" 2>/dev/null || true)
    
    if [ -z "$TUNNEL_PID" ]; then
        log "ERROR: Туннель не запущен! Запускаю..."
        start_tunnel
        return $?
    fi
    
    # Проверяем, жив ли процесс туннеля
    if ! kill -0 $TUNNEL_PID 2>/dev/null; then
        log "ERROR: Туннель (PID $TUNNEL_PID) не отвечает! Перезапускаю..."
        kill $TUNNEL_PID 2>/dev/null || true
        sleep 2
        start_tunnel
        return $?
    fi
    
    return 0
}

# Функция запуска туннеля
start_tunnel() {
    ssh -i "$SSH_KEY" \
        -p $SSH_PORT \
        -N \
        -R ${REMOTE_PORT}:localhost:${REMOTE_PORT} \
        -o ServerAliveInterval=15 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -o StrictHostKeyChecking=no \
        -o TCPKeepAlive=yes \
        -f \
        ${SSH_USER}@${SSH_HOST} \
        "echo 'Tunnel established'"
    
    if [ $? -eq 0 ]; then
        TUNNEL_PID=$(pgrep -f "ssh.*-R.*$REMOTE_PORT.*$SSH_HOST" | head -1)
        log "✓ Туннель запущен (PID: $TUNNEL_PID)"
        return 0
    else
        log "✗ Ошибка запуска туннеля!"
        return 1
    fi
}

# Основная петля мониторинга
log "Запуск мониторинга..."

# Проверка SSH ключа
if [ ! -f "$SSH_KEY" ]; then
    log "ERROR: SSH ключ не найден: $SSH_KEY"
    exit 1
fi

# Первичная проверка
check_tunnel
TUNNEL_STATUS=$?

if [ $TUNNEL_STATUS -ne 0 ]; then
    log "ERROR: Не удалось запустить туннель. Проверьте подключение к серверу."
    exit 1
fi

# Запускаем мониторинг
while true; do
    sleep 30
    
    # Проверяем туннель
    if ! check_tunnel; then
        log "Туннель успешно восстановлен"
    else
        echo "."  # Тихий статус
    fi
done
