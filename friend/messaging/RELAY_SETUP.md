# MAX Bot — Relay Server Setup (без домена, только IP)

## Архитектура

```
MAX Platform
    │
    │  webhook POST (HTTPS)
    ▼
┌──────────────────────────┐
│ Удалённый сервер (IP)    │
│                          │
│  max_webhook_relay.py    │
│  (порт 443, HTTPS)       │
│       │                  │
│       │  HTTP localhost  │
│       ▼                  │
│  Django (8000)           │
└──────────────────────────┘
```

## Установка

### 1. Скопируйте relay

```bash
scp friend/messaging/max_webhook_relay.py user@server:/opt/max-bot-relay/
```

### 2. Настройте firewall

```bash
# Разрешите порт 443 (HTTPS)
sudo ufw allow 443/tcp
sudo ufw reload
```

### 3. Сгенерируйте самоподписанный сертификат

```bash
cd /opt/max-bot-relay
python3 max_webhook_relay.py \
    --generate-cert \
    --cert cert.pem \
    --key key.pem
```

### 4. Запустите relay

```bash
python3 /opt/max-bot-relay/max_webhook_relay.py \
    --local-url http://127.0.0.1:8000 \
    --port 443 \
    --cert /opt/max-bot-relay/cert.pem \
    --key /opt/max-bot-relay/key.pem
```

### 5. Настройте Django

В `friend/settings.py` на локальной машине:

```python
# Укажите IP удалённого сервера
MAX_WEBHOOK_URL = 'https://123.45.67.89/max/webhook/'
```

### 6. Зарегистрируйте webhook

```bash
python3 manage.py runmaxbot --subscribe
```

## Автоматический запуск (systemd)

```bash
sudo tee /etc/systemd/system/max-webhook-relay.service << 'EOF'
[Unit]
Description=MAX Webhook Relay
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/max-bot-relay
ExecStart=/usr/bin/python3 /opt/max-bot-relay/max_webhook_relay.py \
    --local-url http://127.0.0.1:8000 \
    --port 443 \
    --cert /opt/max-bot-relay/cert.pem \
    --key /opt/max-bot-relay/key.pem
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable max-webhook-relay
sudo systemctl start max-webhook-relay
```

## Проверка

```bash
# Проверка relay
curl -k https://123.45.67.89/health

# Проверка логов
sudo journalctl -u max-webhook-relay -f
```

## Troubleshooting

### 1. MAX не может достучаться до сервера

```bash
# Проверьте firewall
sudo ufw status

# Проверьте порт
sudo ss -tlnp | grep 443
```

### 2. Relay не может подключиться к Django

```bash
# Проверьте Django
curl http://127.0.0.1:8000/api/max/webhook/

# Проверьте логи
sudo journalctl -u max-webhook-relay -n 50
```

### 3. Ошибка SSL

```bash
# Проверьте сертификаты
ls -la /opt/max-bot-relay/cert.pem
ls -la /opt/max-bot-relay/key.pem

# Пересоздайте сертификаты
python3 max_webhook_relay.py --generate-cert --cert cert.pem --key key.pem
```

## Примечания

- Самоподписанный сертификат не проверяется MAX — они принимают любой валидный SSL
- Если MAX требует проверку сертификата, используйте Let's Encrypt с доменом
- Порт 443 требует root-права. Если не хотите запускать от root, используйте порт >1024
