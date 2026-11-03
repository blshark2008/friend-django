# SIEM Agent — установка на хост

## 1. Создание токена

```bash
python manage.py drf_create_token blshark
```

## 2. Развёртывание агента

```bash
# На хосте Astra Linux
sudo mkdir -p /opt/siem /var/lib/siem-agent
sudo cp agent.sh /opt/siem/agent.sh
sudo cp config.env.example /opt/siem/config.env
sudo chmod +x /opt/siem/agent.sh
```

Заполните `/opt/siem/config.env`:

```bash
SIEM_SERVER="https://127.0.0.1:8000"
SIEM_TOKEN="d0081ff08ceea3758134b079631f2b49533cf5b4"
```

## 3. Cron-расписание

```bash
sudo tee /etc/cron.d/siem-agent << 'EOF'
# SIEM Agent — каждые 5 минут
*/5 * * * * root /opt/siem/agent.sh
# Инвентаризация — каждый день в 2:00
0 2 * * * root /opt/siem/agent.sh daily
EOF
```

## 4. Проверка

```bash
# Ручной запуск
/opt/siem/agent.sh

# Проверка агентов с сервера
python manage.py check_agents --alert

# Очистка старых данных (90 дней)
python manage.py cleanup_retention --days 90
```

## API-эндпоинты

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/siem/ingest/` | Принять события от агента |
| POST | `/api/siem/ingest/inventory/` | Принять снимок инвентаризации |
| GET | `/api/siem/dashboard/` | Сводная статистика |
| GET | `/api/siem/hosts/` | Список хостов |
| GET | `/api/siem/events/` | Список событий |

## Management-команды

| Команда | Описание |
|---|---|
| `check_agents --alert` | Проверить здоровье агентов |
| `cleanup_retention --days 90` | Очистить старые события |
| `cleanup_retention --dry-run` | Показать что будет удалено |
