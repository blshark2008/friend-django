#!/bin/bash
# ============================================================================
# Перезапуск SSH reverse tunnel
# ============================================================================
# Запуск на локальной машине:
#   bash deploy/restart_tunnel.sh
# ============================================================================

SSH_USER="pechea"
SSH_HOST="84.54.59.213"
SSH_KEY="$HOME/.ssh/id_ed25519"
REMOTE_PORT=8000
LOCAL_PORT=8000

echo "============================================"
echo "  Перезапуск SSH reverse tunnel"
echo "============================================"
echo ""

# Останавливаем старый туннель
TUNNEL_PID=$(pgrep -f "ssh.*-R.*$REMOTE_PORT.*$SSH_HOST" 2>/dev/null || true)
if [ -n "$TUNNEL_PID" ]; then
    echo "[1/3] Остановка старого туннеля (PID: $TUNNEL_PID)..."
    kill $TUNNEL_PID 2>/dev/null || true
    sleep 2
    echo "  ✓ Остановлен"
else
    echo "[1/3] Старый туннель не найден"
fi

# Запускаем новый туннель
echo ""
echo "[2/3] Запуск нового туннеля..."

ssh -i "$SSH_KEY" \
    -p 22 \
    -N \
    -R ${REMOTE_PORT}:localhost:${LOCAL_PORT} \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -o StrictHostKeyChecking=no \
    -f \
    ${SSH_USER}@${SSH_HOST} \
    "echo 'Tunnel established'"

if [ $? -eq 0 ]; then
    TUNNEL_PID=$(pgrep -f "ssh.*-R.*$REMOTE_PORT.*$SSH_HOST" | head -1)
    echo "  ✓ Туннель запущен (PID: $TUNNEL_PID)"
else
    echo "ERROR: Не удалось запустить туннель"
    exit 1
fi

# Регистрируем webhook
echo ""
echo "[3/3] Перерегистрация webhook в MAX API..."

python manage.py runmaxbot --subscribe 2>&1 || {
    echo "  WARNING: Ошибка перерегистрации webhook"
}

echo ""
echo "============================================"
echo "  ✓ Туннель перезапущен"
echo "  Webhook URL: https://$SSH_HOST/max/webhook/"
echo "============================================"
echo ""
