#!/bin/bash
# ============================================================================
# Генерация self-signed SSL сертификата для сервера 84.54.59.213
# ============================================================================
# Запуск на сервере:
#   ssh pechea@84.54.59.213
#   bash deploy/setup_ssl.sh
# ============================================================================

set -e

echo "============================================"
echo "  Генерация SSL сертификата"
echo "============================================"
echo ""

SSL_DIR="/etc/nginx/ssl"

# Создаём директорию
sudo mkdir -p "$SSL_DIR"

# Генерируем self-signed сертификат (действует 10 лет)
echo "Генерация сертификата..."
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout "$SSL_DIR/friend.key" \
    -out "$SSL_DIR/friend.crt" \
    -subj "/C=RU/ST=Novosibirsk/L=Novosibirsk/O=Friend/OU=Dev/CN=84.54.59.213" \
    -addext "subjectAltName=IP:84.54.59.213"

# Устанавливаем права
sudo chmod 600 "$SSL_DIR/friend.key"
sudo chmod 644 "$SSL_DIR/friend.crt"

echo ""
echo "============================================"
echo "  ✓ SSL сертификат создан"
echo "============================================"
echo ""
echo "  Сертификат: $SSL_DIR/friend.crt"
echo "  Ключ:       $SSL_DIR/friend.key"
echo "  Действует:  10 лет"
echo ""
echo "  Проверка:"
echo "  openssl x509 -in $SSL_DIR/friend.crt -text -noout"
echo ""
