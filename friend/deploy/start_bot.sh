#!/bin/bash
# ============================================================================
# Запуск бота MAX на локальной машине
# ============================================================================
# Запуск:
#   bash deploy/start_bot.sh
#
# Скрипт:
#   1. Проверяет, запущен ли Django
#   2. Запускает туннель до сервера
#   3. Регистрирует webhook в MAX API
# ============================================================================

set -e

# ============================================================================
# НАСТРОЙКИ
# ============================================================================
SSH_USER="pechea"
SSH_HOST="84.54.59.213"
SSH_KEY="$HOME/.ssh/id_ed25519"
SSH_PORT=22
REMOTE_PORT=8000
DJANGO_PORT=8000
WEBHOOK_URL="https://projectgame.ru/max/webhook/"
LOG_FILE="/tmp/bot_start.log"

# ============================================================================
# ФУНКЦИИ
# ============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_prerequisites() {
    log "Проверка зависимостей..."
    
    # Проверяем Python
    if ! command -v python3 &> /dev/null; then
        log "ERROR: python3 не установлен"
        exit 1
    fi
    
    # Проверяем SSH
    if ! command -v ssh &> /dev/null; then
        log "ERROR: ssh не установлен"
        exit 1
    fi
    
    # Проверяем SSH ключ
    if [ ! -f "$SSH_KEY" ]; then
        log "ERROR: SSH ключ не найден: $SSH_KEY"
        log "Создайте ключ: ssh-keygen -t ed25519"
        exit 1
    fi
    
    # Проверяем, что проект существует
    if [ ! -f "manage.py" ]; then
        log "ERROR: manage.py не найден. Запустите скрипт из корня проекта"
        exit 1
    fi
    
    log "✓ Все зависимости есть"
}

start_django() {
    log "Запуск Django на порту $DJANGO_PORT..."
    
    # Проверяем, запущен ли уже Django
    if lsof -i :$DJANGO_PORT &> /dev/null; then
        log "⚠ Django уже запущен на порту $DJANGO_PORT"
        log "Перезапускаю..."
        pgrep -f "manage.py runserver" | xargs kill 2>/dev/null || true
        sleep 2
    fi
    
    # Запускаем Django в фоне
    python3 manage.py runserver 0.0.0.0:$DJANGO_PORT > /tmp/django.log 2>&1 &
    DJANGO_PID=$!
    
    # Ждём запуска
    log "Ожидание запуска Django..."
    for i in {1..10}; do
        if lsof -i :$DJANGO_PORT &> /dev/null; then
            log "✓ Django запущен (PID: $DJANGO_PID)"
            return 0
        fi
        sleep 1
    done
    
    log "ERROR: Django не запустился. Проверьте /tmp/django.log"
    cat /tmp/django.log
    exit 1
}

start_tunnel() {
    log "Запуск SSH-туннеля..."
    
    # Проверяем, запущен ли уже туннель
    TUNNEL_PID=$(pgrep -f "ssh.*-R.*$REMOTE_PORT.*$SSH_HOST" 2>/dev/null || true)
    if [ -n "$TUNNEL_PID" ]; then
        log "⚠ Туннель уже запущен (PID: $TUNNEL_PID)"
        log "Перезапускаю..."
        kill $TUNNEL_PID 2>/dev/null || true
        sleep 2
    fi
    
    # Запускаем туннель
    ssh -i "$SSH_KEY" \
        -p $SSH_PORT \
        -N \
        -R ${REMOTE_PORT}:localhost:${DJANGO_PORT} \
        -o ServerAliveInterval=30 \
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
        log "  Локально: localhost:$DJANGO_PORT"
        log "  На сервере: 0.0.0.0:$REMOTE_PORT"
    else
        log "ERROR: Не удалось запустить туннель"
        exit 1
    fi
}

register_webhook() {
    log "Регистрация webhook в MAX API..."
    
    python3 -c "
import os, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'friend.settings')
django.setup()

from messaging.services.max_api import MAXClient
from django.conf import settings

client = MAXClient()
webhook_url = settings.MAX_WEBHOOK_URL
secret = settings.MAX_WEBHOOK_SECRET

print(f'Webhook URL: {webhook_url}')

# Подписываемся на события
try:
    result = client.subscribe_webhook(
        url=webhook_url,
        update_types=['message_created', 'message_callback', 'bot_started', 'bot_added'],
        secret=secret,
    )
    print(f'✓ Webhook зарегистрирован')
    print(f'  Update types: message_created, message_callback, bot_started, bot_added')
except Exception as e:
    print(f'ERROR: {e}')
    exit(1)
"
    
    if [ $? -eq 0 ]; then
        log "✓ Webhook зарегистрирован"
    else
        log "ERROR: Не удалось зарегистрировать webhook"
        exit 1
    fi
}

test_webhook() {
    log "Тестирование webhook..."
    
    # Проверяем, что туннель работает
    for i in {1..5}; do
        RESPONSE=$(curl -k -s -o /dev/null -w "%{http_code}" https://$SSH_HOST/nginx-health 2>/dev/null || echo "000")
        if [ "$RESPONSE" = "200" ]; then
            log "✓ Туннель работает (nginx-health: 200)"
            break
        fi
        log "  Проверка... ($i/5)"
        sleep 2
    done
    
    # Тестируем webhook
    TEST_RESPONSE=$(curl -k -s -X POST https://$SSH_HOST/max/webhook/ \
        -H "Content-Type: application/json" \
        -d '{"update_type":"bot_started","chat_id":999999999,"user":{"user_id":999999999}}' 2>/dev/null)
    
    if echo "$TEST_RESPONSE" | grep -q '"status": "ok"'; then
        log "✓ Webhook отвечает корректно"
    else
        log "⚠ Webhook не отвечает корректно: $TEST_RESPONSE"
    fi
}

show_status() {
    echo ""
    echo "============================================"
    echo "  Статус бота MAX"
    echo "============================================"
    echo ""
    
    # Django
    if lsof -i :$DJANGO_PORT &> /dev/null; then
        DJANGO_PID=$(lsof -i :$DJANGO_PORT | grep LISTEN | awk '{print $2}')
        log "✓ Django запущен (PID: $DJANGO_PID)"
    else
        log "✗ Django НЕ запущен"
    fi
    
    # Туннель
    TUNNEL_PID=$(pgrep -f "ssh.*-R.*$REMOTE_PORT.*$SSH_HOST" | head -1)
    if [ -n "$TUNNEL_PID" ]; then
        log "✓ Туннель запущен (PID: $TUNNEL_PID)"
    else
        log "✗ Туннель НЕ запущен"
    fi
    
    # Webhook
    if curl -k -s https://$SSH_HOST/max/webhook/ > /dev/null 2>&1; then
        log "✓ Webhook доступен"
    else
        log "✗ Webhook НЕ доступен"
    fi
    
    echo ""
    echo "Логи:"
    echo "  Django:    /tmp/django.log"
    echo "  Bot:       /tmp/django_max_bot.log"
    echo "  Start:     $LOG_FILE"
    echo ""
    echo "Команды:"
    echo "  tail -f /tmp/django_max_bot.log  # Логи бота"
    echo "  tail -f /tmp/django.log          # Логи Django"
    echo "  bash deploy/start_bot.sh         # Перезапустить"
    echo ""
}

# ============================================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================================

log "============================================"
log "  Запуск бота MAX"
log "============================================"
log ""

# Проверка зависимостей
check_prerequisites

# Запуск Django
start_django

# Запуск туннеля
start_tunnel

# Регистрация webhook
register_webhook

# Тестирование
test_webhook

# Показ статуса
show_status

log "✓ Бот MAX запущен!"
log ""
