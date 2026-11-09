# SSH Reverse Tunnel для MAX Webhook

## Архитектура

```
MAX Platform API
       │
       │  POST https://84.54.59.213/max/webhook/
       ▼
┌──────────────────────────────┐
│ Сервер 84.54.59.213          │
│                              │
│  Nginx (HTTPS :443)          │
│       ↓ прокси               │
│  localhost:8000              │
│       ↓ SSH reverse tunnel   │
└───────┬──────────────────────┘
        │
        │  SSH -R 8000:localhost:8000
        ▼
┌──────────────────────────────┐
│ Локальная машина             │
│                              │
│  Django (localhost:8000)     │
│                              │
└──────────────────────────────┘
```

## Быстрый старт

### 1. Деплой на сервер

```bash
# На локальной машине:
bash deploy/deploy.sh
```

Этот скрипт:
- Копирует nginx-конфиг и SSL-скрипты на сервер
- Генерирует self-signed SSL сертификат
- Настраивает и запускает nginx
- Регистрирует webhook в MAX API

### 2. Запуск Django

```bash
# На локальной машине:
python manage.py runserver 0.0.0.0:8000
```

### 3. Запуск SSH reverse tunnel

```bash
# На локальной машине:
bash deploy/start_tunnel.sh
```

Этот скрипт:
- Запускает Django (если не запущен)
- Создаёт SSH reverse tunnel: сервер:8000 → localhost:8000
- Настраивает постоянство соединения (ServerAliveInterval)

### 4. Проверка

```bash
# Проверка nginx на сервере:
curl -k https://84.54.59.213/nginx-health

# Проверка webhook:
curl -X POST https://84.54.59.213/max/webhook/ \
  -H "Content-Type: application/json" \
  -d '{"update_type":"test","message":{}}'
```

## Файлы

| Файл | Где | Описание |
|------|-----|----------|
| `deploy/deploy.sh` | Локально | Полный деплой на сервер |
| `deploy/start_tunnel.sh` | Локально | Запуск SSH reverse tunnel |
| `deploy/restart_tunnel.sh` | Локально | Перезапуск туннеля |
| `deploy/setup_ssl.sh` | Сервер | Генерация SSL сертификата |
| `deploy/setup_nginx.sh` | Сервер | Настройка nginx |
| `deploy/nginx-friend.conf` | Сервер | Конфиг nginx |

## Команды

### Запуск всего

```bash
# 1. Деплой (один раз):
bash deploy/deploy.sh

# 2. Запуск Django:
python manage.py runserver 0.0.0.0:8000

# 3. Запуск туннеля:
bash deploy/start_tunnel.sh
```

### Перезапуск туннеля

```bash
bash deploy/restart_tunnel.sh
```

### Остановка

```bash
# Остановка туннеля:
pkill -f "ssh.*-R.*8000.*84.54.59.213"

# Остановка Django:
pkill -f "runserver"
```

### Ручной SSH reverse tunnel

```bash
ssh -i ~/.ssh/id_ed25519 \
    -N \
    -R 8000:localhost:8000 \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    pechea@84.54.59.213
```

## Troubleshooting

### Туннель не подключается

```bash
# Проверьте подключение к серверу:
ssh -i ~/.ssh/id_ed25519 pechea@84.54.59.213

# Проверьте, что Django запущен:
lsof -i :8000

# Проверьте, что туннель запущен:
pgrep -f "ssh.*-R.*8000"
```

### Nginx не проксирует

```bash
# Проверьте конфиг nginx:
sudo nginx -t

# Проверьте логи:
sudo tail -f /var/log/nginx/error.log

# Проверьте, что порт 8000 на сервере проброшен:
curl http://localhost:8000/nginx-health
```

### Webhook не работает

```bash
# 1. Проверьте URL в settings.py:
grep MAX_WEBHOOK_URL friend/settings.py

# 2. Перерегистрируйте webhook:
python manage.py runmaxbot --subscribe

# 3. Проверьте логи Django:
tail -f logs/django.log
```

### Туннель разорвался

```bash
# Перезапустите туннель:
bash deploy/restart_tunnel.sh
```
