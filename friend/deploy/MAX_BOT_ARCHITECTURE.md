# MAX Bot — Надёжная архитектура взаимодействия

## Проблема, которую решили

Ранее `chat_id` хранился только в памяти (`session_store` в `max_bot.py`). При перезапуске Django все `chat_id` терялись, и бот не мог отвечать пользователям.

## Решение

### 1. Сохранение chat_id в БД

- Добавлено поле `max_chat_id` в модель `accounts.User`
- `chat_id` сохраняется при:
  - `bot_started` — когда пользователь запускает бота
  - `message_created` — при первом сообщении от пользователя
  - Регистрации (`/register`) — при успешной регистрации

### 2. Приоритет получения chat_id

Функция `_get_user_chat_id()` в `messaging/views.py`:
1. Сначала проверяет БД (`user.max_chat_id`) — надёжно, сохраняется между перезапусками
2. Затем проверяет `session_store` — для быстрых ответов
3. В конце возвращает `None` — если не найден нигде

### 3. Fallback при отправке сообщений

Функция `_send_message_to_user()`:
1. Сначала пытается отправить с `chat_id`
2. При ошибке — повторяет только с `user_id`
3. Логгирует все попытки для отладки

### 4. Подписка на message_callback

Webhook теперь подписан на:
- `message_created` — текстовые сообщения
- `message_callback` — нажатия кнопок
- `bot_started` — запуск бота
- `bot_added` — добавление бота в чат

### 5. Мониторинг туннеля

Новый скрипт `deploy/monitor_tunnel.sh`:
- Проверяет туннель каждые 30 секунд
- Автоматически переподключается при обрыве
- Логгирует все события в `/tmp/tunnel_monitor.log`

## Использование

### Запуск бота

```bash
# 1. Запуск Django
python manage.py runserver 0.0.0.0:8000

# 2. Запуск туннеля
bash deploy/start_tunnel.sh

# 3. Регистрация webhook
python manage.py runmaxbot --subscribe
```

### Мониторинг туннеля

```bash
# Запуск мониторинга с автовосстановлением
bash deploy/monitor_tunnel.sh
```

### Проверка работы

```bash
# Проверка туннеля
curl -k https://projectgame.ru/nginx-health

# Проверка логов
tail -f /tmp/django_max_bot.log
tail -f /tmp/tunnel_monitor.log
```

## Структура файлов

```
messaging/
├── views.py              # Webhook handler с сохранением chat_id в БД
├── bots/
│   └── max_bot.py        # Обработчики команд с сохранением chat_id
├── management/
│   └── commands/
│       └── runmaxbot.py  # Long Polling с подпиской на message_callback
└── services/
    ├── max_api.py        # MAX API client
    └── bot_api_client.py # Wrapper для bot API

deploy/
├── start_tunnel.sh       # Запуск туннеля
├── monitor_tunnel.sh     # Мониторинг с автовосстановлением
├── deploy.sh             # Полный деплой
└── nginx-friend.conf     # Nginx конфиг

accounts/
└── models.py             # Модель User с полем max_chat_id
```

## Логирование

Все события логируются в `/tmp/django_max_bot.log`:
- Входящие webhook события
- Сохранение chat_id
- Отправка сообщений
- Ошибки обработки

Мониторинг туннеля логируется в `/tmp/tunnel_monitor.log`:
- Запуск/остановка туннеля
- Переподключения
- Ошибки

## Отладка

Если сообщения не доходят:

1. Проверьте туннель:
   ```bash
   curl -k https://projectgame.ru/nginx-health
   ```

2. Проверьте логи Django:
   ```bash
   tail -f /tmp/django_max_bot.log | grep -E "chat_id|message_callback"
   ```

3. Проверьте, что chat_id сохранён в БД:
   ```python
   python manage.py shell
   >>> from accounts.models import User
   >>> User.objects.filter(max_id='USER_ID').values('max_chat_id')
   ```

4. Проверьте туннель:
   ```bash
   tail -f /tmp/tunnel_monitor.log
   ```
