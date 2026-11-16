#!/bin/bash
# Скрипт для настройки SSH reverse tunnel и деплоя nginx конфига
# Запускать с локальной машины

SERVER_USER="user"
SERVER_IP="84.54.59.213"
LOCAL_PORT="8000"
REMOTE_PORT="2222"  # Порт для reverse tunnel

# ============================================
# Шаг 1: Деплой nginx конфига на сервер
# ============================================
echo "📤 Деплой nginx конфига на сервер..."
scp deploy/nginx-friend.conf ${SERVER_USER}@${SERVER_IP}:/tmp/nginx-friend.conf

# ============================================
# Шаг 2: Настройка и перезапуск nginx на сервере
# ============================================
echo "⚙️  Настройка nginx на сервере..."
ssh ${SERVER_USER}@${SERVER_IP} << 'EOF'
# Копируем конфиг
sudo cp /tmp/nginx-friend.conf /etc/nginx/sites-available/friend

# Проверяем конфиг
sudo nginx -t

# Перезапускаем nginx
sudo systemctl reload nginx

# Проверяем статус
sudo systemctl status nginx --no-pager -l
EOF

# ============================================
# Шаг 3: Создание SSH reverse tunnel
# ============================================
# Запускает туннель, который пробрасывает localhost:8000 на сервер
# Запускать в фоновом режиме или через nohup/screen/tmux

echo ""
echo "🔗 SSH reverse tunnel:"
echo "  Запустите в отдельной терминальной сессии:"
echo ""
echo "  ssh -N -R ${REMOTE_PORT}:localhost:${LOCAL_PORT} ${SERVER_USER}@${SERVER_IP}"
echo ""
echo "  Или в фоновом режиме:"
echo "  ssh -N -f -R ${REMOTE_PORT}:localhost:${LOCAL_PORT} ${SERVER_USER}@${SERVER_IP}"
echo ""
echo "  Для остановки:"
echo "  pkill -f 'ssh.*-R.*${REMOTE_PORT}.*${SERVER_IP}'"
echo ""

# ============================================
# Шаг 4: Настройка systemd service для tunnel (опционально)
# ============================================
echo "📝 Для автозапуска туннеля создайте service на сервере:"
echo ""
echo "  sudo nano /etc/systemd/system/django-tunnel.service"
echo ""
echo "  [Unit]"
echo "  Description=Django SSH Reverse Tunnel"
echo "  After=network.target"
echo ""
echo "  [Service]"
echo "  User=${SERVER_USER}"
echo "  ExecStart=/usr/bin/ssh -N -f -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -R ${REMOTE_PORT}:localhost:${LOCAL_PORT} ${SERVER_USER}@${SERVER_IP}"
echo "  Restart=always"
echo "  RestartSec=10"
echo ""
echo "  [Install]"
echo "  WantedBy=multi-user.target"
echo ""
echo "  Затем:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now django-tunnel"
echo ""

echo "✅ Готово!"
echo ""
echo "🌐 Доступ к приложению: https://friend.projectgame.ru"
