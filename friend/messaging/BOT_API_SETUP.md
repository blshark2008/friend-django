# MAX Bot API — Инструкция по установке

## Архитектура

```
MAX Platform (Long Polling)
         │
         ▼
┌──────────────────────────────┐
│ Сервер 84.54.59.213          │
│                              │
│  bot_api.py (API на порту 5000) │
│                              │
│  MAX Bot (Long Polling)      │
└──────────────────────────────┘
         │
         │  HTTP
         ▼
┌──────────────────────────────┐
│ Локальная машина             │
│                              │
│  Django (8000)               │
│  вызывает API на 84.54.59.213│
└──────────────────────────────┘
```

## Установка на сервере 84.54.59.213

### 1. Скопируйте файлы

```bash
scp messaging/bot_api.py pechea@84.54.59.213:/opt/max-bot-api/
```

### 2. Запустите API

```bash
ssh -i ~/.ssh/id_ed25519 pechea@84.54.59.213

# На сервере
cd ~/max-bot-api
python3 bot_api.py --port 5000 --token 'f9LHodD0cOIYMz2y4innjHTr1GbEaOS0kX_FdLooS7xj1JzkdrVufdvwwwpOmfJ8vaemQcwdhNJOz8b52Sdw'
```

### 3. Проверьте

```bash
curl http://84.54.59.213:5000/api/health
```

Должно ответить:
```json
{"status": "ok", "timestamp": "..."}
```

## Настройка Django

### 1. Проверьте настройки

```python
# friend/settings.py
MAX_BOT_API_URL = 'http://84.54.59.213:5000'
```

### 2. Запустите сценарий

1. Откройте `http://127.0.0.1:8000/scenarios/`
2. Нажмите "Запустить"
3. Django вызовет API на сервере для отправки сообщений

## Автоматический запуск (systemd)

```bash
sudo tee /etc/systemd/system/max-bot-api.service << 'EOF'
[Unit]
Description=MAX Bot API Server
After=network.target

[Service]
Type=simple
User=pechea
WorkingDirectory=/opt/max-bot-api
ExecStart=/usr/bin/python3 /opt/max-bot-api/bot_api.py --port 5000 --token 'f9LHodD0cOIYMz2y4innjHTr1GbEaOS0kX_FdLooS7xj1JzkdrVufdvwwwpOmfJ8vaemQcwdhNJOz8b52Sdw'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable max-bot-api
sudo systemctl start max-bot-api
```

## API Endpoints

### POST /api/send-message
Отправить сообщение пользователю.

```json
{
    "user_id": 15284524,
    "text": "Привет, мир!",
    "format": "html"
}
```

### POST /api/run-scenario
Запустить сценарий.

```json
{
    "scenario_id": 1,
    "started_by": 75
}
```

### POST /api/process-answer
Обработать ответ пользователя.

```json
{
    "user_id": 15284524,
    "button_result_code": "WYG2X6GE"
}
```

### GET /api/health
Проверить здоровье API.

```json
{"status": "ok", "timestamp": "..."}
```

## Troubleshooting

### 1. API не отвечает

```bash
# Проверьте, запущен ли процесс
ps aux | grep bot_api.py

# Проверьте порт
sudo ss -tlnp | grep 5000

# Проверьте логи
sudo journalctl -u max-bot-api -f
```

### 2. Django не может подключиться

```bash
# Проверьте брандмауэр
sudo ufw status

# Разрешите порт
sudo ufw allow 5000/tcp
```

### 3. Ошибка отправки сообщения

Проверьте логи Django:
```bash
tail -f /path/to/friend/logs/django.log
```

И логи API:
```bash
sudo journalctl -u max-bot-api -f
```
