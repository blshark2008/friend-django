#!/bin/bash
# ============================================================================
# Запуск SSH reverse tunnel: сервер 84.54.59.213 → локальный Django
# ============================================================================
# Запуск на локальной машине:
#   bash deploy/start_tunnel.sh
#
# Схема:
#   MAX API → https://84.54.59.213/max/webhook/
#       ↓
#     Nginx (сервер, порт 8000)
#       ↓
#     SSH reverse tunnel
#       ↓
#     Локальный Django (localhost:8000)
# ============================================================================

set -e

SSH_USER="pechea"
SSH_HOST="84.54.59.213"
SSH_KEY="$HOME/.ssh/id_ed25519"
SSH_PORT=22
REMOTE_PORT=8000
LOCAL_PORT=8000

echo "============================================"
echo "  SSH Reverse Tunnel"
echo "============================================"
echo ""
echo "  Сервер:   $SSH_HOST"
echo "  Локально: localhost:$LOCAL_PORT (Django)"
echo "  На сервере: порт $REMOTE_PORT → localhost:$LOCAL_PORT"
echo ""

# ============================================================================
# Проверка зависимостей
# ============================================================================

# Проверка SSH ключа
if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: SSH ключ не найден: $SSH_KEY"
    echo "  Используйте: ssh -i $SSH_KEY $SSH_USER@$SSH_HOST"
    exit 1
fi

# Проверка Django
if ! python manage.py check &>/dev/null; then
    echo "WARNING: Django check failed. Запустите миграции:"
    echo "  python manage.py migrate"
    echo ""
    read -p "  Продолжить? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# ============================================================================
# Запуск Django в фоне
# ============================================================================
echo "[1/2] Запуск Django..."

# Проверяем, не запущен ли уже Django
if lsof -i :$LOCAL_PORT &>/dev/null; then
    echo "  Django уже запущен на порту $LOCAL_PORT"
else
    python manage.py runserver 0.0.0.0:$LOCAL_PORT &
    DJANGO_PID=$!
    sleep 2
    
    # Проверяем, что Django запустился
    if ! lsof -i :$LOCAL_PORT &>/dev/null; then
        echo "ERROR: Django не запустился"
        exit 1
    fi
    echo "  ✓ Django запущен (PID: $DJANGO_PID)"
fi

# ============================================================================
# Запуск SSH reverse tunnel
# ============================================================================
echo ""
echo "[2/2] Запуск SSH reverse tunnel..."

# Проверяем, нет ли уже запущенного туннеля
TUNNEL_PID=$(pgrep -f "ssh.*-R.*$REMOTE_PORT.*$SSH_HOST" 2>/dev/null || true)
if [ -n "$TUNNEL_PID" ]; then
    echo "  Туннель уже запущен (PID: $TUNNEL_PID)"
    echo "  Для перезапуска: bash deploy/restart_tunnel.sh"
    echo ""
    read -p "  Продолжить? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Запускаем туннель
ssh -i "$SSH_KEY" \
    -p $SSH_PORT \
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
    echo "  Проверьте подключение к серверу:"
    echo "  ssh -i $SSH_KEY $SSH_USER@$SSH_HOST"
    exit 1
fi

# ============================================================================
# Итог
# ============================================================================
echo ""
echo "============================================"
echo "  ✓ Готово!"
echo "============================================"
echo ""
echo "  Webhook URL: https://$SSH_HOST/max/webhook/"
echo "  Django:      http://localhost:$LOCAL_PORT"
echo "  Туннель PID: $TUNNEL_PID"
echo ""
echo "  Для остановки:"
echo "    kill $TUNNEL_PID"
echo "    kill $DJANGO_PID 2>/dev/null || true"
echo ""
echo "  Следующие шаги:"
echo "  1. На сервере: bash deploy/setup_ssl.sh"
echo "  2. На сервере: bash deploy/setup_nginx.sh"
echo "  3. Зарегистрировать webhook:"
echo "     python manage.py runmaxbot --subscribe"
echo ""
