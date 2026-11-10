#!/bin/bash
# ============================================================================
# Настройка Nginx на сервере 84.54.59.213
# ============================================================================
# Запуск на сервере:
#   ssh pechea@84.54.59.213
#   bash deploy/setup_nginx.sh
# ============================================================================

set -e

echo "============================================"
echo "  Настройка Nginx на 84.54.59.213"
echo "============================================"
echo ""

# ============================================================================
# 1. Установка Nginx
# ============================================================================
echo "[1/4] Установка Nginx..."

if ! command -v nginx &>/dev/null; then
    sudo apt update
    sudo apt install -y nginx
    echo "  ✓ Nginx установлен"
else
    echo "  ✓ Nginx уже установлен"
fi

# ============================================================================
# 2. Установка SSL сертификата
# ============================================================================
echo ""
echo "[2/4] Проверка SSL сертификата..."

SSL_DIR="/etc/nginx/ssl"
SSL_CRT="$SSL_DIR/friend.crt"
SSL_KEY="$SSL_DIR/friend.key"

if [ ! -f "$SSL_CRT" ] || [ ! -f "$SSL_KEY" ]; then
    echo "  SSL сертификат не найден. Запустите: bash deploy/setup_ssl.sh"
    exit 1
else
    echo "  ✓ SSL сертификат найден"
fi

# ============================================================================
# 3. Установка конфига Nginx
# ============================================================================
echo ""
echo "[3/4] Установка конфига Nginx..."

NGINX_CONF="/etc/nginx/sites-available/friend"
NGINX_LINK="/etc/nginx/sites-enabled/friend"

# Удаляем старый конфиг если есть
sudo rm -f "$NGINX_LINK"

# Копируем конфиг (ожидается, что файл скопирован на сервер)
DEPLOY_CONF="/home/pechea/deploy/nginx-friend.conf"
if [ -f "$DEPLOY_CONF" ]; then
    sudo cp "$DEPLOY_CONF" "$NGINX_CONF"
    echo "  ✓ Конфиг скопирован из deploy/"
else
    # Создаём конфиг напрямую
    echo "  Создаю конфиг Nginx..."
    sudo tee "$NGINX_CONF" > /dev/null <<'NGINX_EOF'
server {
    listen 443 ssl http2;
    server_name 84.54.59.213 projectgame.ru www.projectgame.ru;

    ssl_certificate     /etc/nginx/ssl/friend.crt;
    ssl_certificate_key /etc/nginx/ssl/friend.key;
    
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location /max/webhook/ {
        proxy_pass http://127.0.0.1:8000/max/webhook/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_read_timeout 30s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        
        client_max_body_size 10M;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Training webhook endpoint
    location /training/ {
        proxy_pass http://127.0.0.1:8000/training/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_read_timeout 30s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        
        client_max_body_size 10M;
    }

    location /nginx-health {
        access_log off;
        return 200 "ok";
        add_header Content-Type text/plain;
    }

    location ~ /\. {
        deny all;
    }
}

server {
    listen 80;
    server_name 84.54.59.213 projectgame.ru www.projectgame.ru;
    
    location /max/webhook/ {
        return 301 https://$host$request_uri;
    }
    
    location /training/ {
        return 301 https://$host$request_uri;
    }
    
    location /api/ {
        return 301 https://$host$request_uri;
    }
}
NGINX_EOF
    echo "  ✓ Конфиг создан"
fi

# Активируем конфиг
sudo ln -sf "$NGINX_CONF" "$NGINX_LINK"

# Удаляем default если есть
sudo rm -f /etc/nginx/sites-enabled/default

# ============================================================================
# 4. Проверка и перезапуск Nginx
# ============================================================================
echo ""
echo "[4/4] Проверка и перезапуск Nginx..."

sudo nginx -t
if [ $? -eq 0 ]; then
    sudo systemctl reload nginx || sudo systemctl start nginx
    echo "  ✓ Nginx перезапущен"
else
    echo "ERROR: Нginx конфиг содержит ошибки"
    exit 1
fi

# ============================================================================
# Итог
# ============================================================================
echo ""
echo "============================================"
echo "  ✓ Nginx настроен!"
echo "============================================"
echo ""
echo "  Webhook URL (MAX): https://projectgame.ru/max/webhook/"
echo "  Webhook URL (Training): https://projectgame.ru/training/webhook/"
echo ""
echo "  Проверка:"
echo "  curl -k https://projectgame.ru/nginx-health"
echo ""
echo "  Логи:"
echo "  sudo tail -f /var/log/nginx/error.log"
echo "  sudo tail -f /var/log/nginx/access.log"
echo ""
