#!/bin/bash
# ============================================================================
# Полный деплой на сервер 84.54.59.213
# ============================================================================
# Запуск на локальной машине:
#   bash deploy/deploy.sh
# ============================================================================

set -e

SSH_USER="pechea"
SSH_HOST="84.54.59.213"
SSH_KEY="$HOME/.ssh/id_ed25519"
REMOTE_DIR="/home/pechea/deploy"

echo "============================================"
echo "  Деплой на сервер 84.54.59.213"
echo "============================================"
echo ""

# ============================================================================
# Шаг 1: Копирование файлов на сервер
# ============================================================================
echo "[1/4] Копирование файлов на сервер..."

# Создаём директорию на сервере
ssh -i "$SSH_KEY" "$SSH_USER@$SSH_HOST" "mkdir -p $REMOTE_DIR"

# Копируем файлы деплоя
scp -i "$SSH_KEY" \
    deploy/nginx-friend.conf \
    deploy/setup_ssl.sh \
    deploy/setup_nginx.sh \
    "$SSH_USER@$SSH_HOST:$REMOTE_DIR/"

echo "  ✓ Файлы скопированы"

# ============================================================================
# Шаг 2: Настройка SSL на сервере
# ============================================================================
echo ""
echo "[2/4] Настройка SSL на сервере..."

ssh -i "$SSH_KEY" "$SSH_USER@$SSH_HOST" "sudo bash $REMOTE_DIR/setup_ssl.sh"

echo "  ✓ SSL настроен"

# ============================================================================
# Шаг 3: Настройка Nginx на сервере
# ============================================================================
echo ""
echo "[3/4] Настройка Nginx на сервере..."

ssh -i "$SSH_KEY" "$SSH_USER@$SSH_HOST" "sudo bash $REMOTE_DIR/setup_nginx.sh"

echo "  ✓ Nginx настроен"

# ============================================================================
# Шаг 4: Регистрация webhook
# ============================================================================
echo ""
echo "[4/4] Регистрация webhook в MAX API..."

# Обновляем MAX_WEBHOOK_URL в settings.py
sed -i "s|MAX_WEBHOOK_URL = '.*'|MAX_WEBHOOK_URL = 'https://$SSH_HOST/max/webhook/'|" friend/settings.py
echo "  ✓ MAX_WEBHOOK_URL обновлён"

# Регистрируем webhook
python manage.py runmaxbot --subscribe 2>&1 || {
    echo "  WARNING: Ошибка регистрации webhook"
    echo "  Запустите вручную: python manage.py runmaxbot --subscribe"
}

echo ""
echo "============================================"
echo "  ✓ Деплой завершён!"
echo "============================================"
echo ""
echo "  Webhook URL (MAX): https://$SSH_HOST/max/webhook/"
echo "  Webhook URL (Training): https://$SSH_HOST/training/webhook/"
echo ""
echo "  Следующие шаги:"
echo "  1. Запустите Django локально:"
echo "     python manage.py runserver 0.0.0.0:8000"
echo ""
echo "  2. Запустите SSH reverse tunnel:"
echo "     bash deploy/start_tunnel.sh"
echo ""
echo "  3. Проверьте:"
echo "     curl -k https://$SSH_HOST/nginx-health"
echo ""
