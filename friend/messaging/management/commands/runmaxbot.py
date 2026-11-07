"""
Команда запуска MAX-бота в polling-режиме.

Использует Long Polling для получения сообщений.
Для production рекомендуется использовать Webhook.

Запуск:
    python manage.py runmaxbot

Настройка в settings.py:
    MAX_BOT_TOKEN = 'your_token_here'
    MAX_API_BASE_URL = 'https://platform-api2.max.ru'
"""

import sys
import time
import signal

from django.core.management.base import BaseCommand
from django.conf import settings

# Глобальный флаг для graceful shutdown
_running = True


def _signal_handler(signum, frame):
    global _running
    _running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


class Command(BaseCommand):
    help = 'Запуск MAX-бота в polling-режиме (Long Polling)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            default=None,
            help='Токен MAX-бота',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='Интервал опроса в секундах (по умолчанию 5)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Тестовый режим: не отправлять ответы',
        )
        parser.add_argument(
            '--subscribe',
            action='store_true',
            help='Зарегистрировать webhook для получения событий',
        )

    def handle(self, *args, **options):
        # Импортируем здесь, чтобы Django мог загрузиться
        from messaging.bots.max_bot import (
            handle_command, handle_message, session_store, BotState,
        )
        from messaging.services.max_api import MAXClient, MAXAPIError

        token = options['token'] or getattr(settings, 'MAX_BOT_TOKEN', '')

        if not token:
            print('ERROR: токен бота не указан. Используйте --token или MAX_BOT_TOKEN в settings.py')
            sys.exit(1)

        dry_run = options['dry_run']
        subscribe = options['subscribe']
        interval = options['interval']

        print('=' * 60)
        print('  MAX Bot — Запуск...')
        print('=' * 60)
        print(f'  Токен: {token[:10]}...{token[-5:]}')
        print(f'  Интервал опроса: {interval}с')
        print(f'  Dry-run: {dry_run}')
        print('=' * 60)
        print('')

        client = MAXClient(token)

        # Регистрация webhook если запрошена
        if subscribe:
            webhook_url = getattr(settings, 'MAX_WEBHOOK_URL', '')
            if not webhook_url:
                print('WARNING: MAX_WEBHOOK_URL не настроен в settings.py')
                print('         Webhook не будет зарегистрирован.')
            else:
                secret = getattr(settings, 'MAX_WEBHOOK_SECRET', '')
                try:
                    result = client.subscribe_webhook(
                        url=webhook_url,
                        update_types=['message_created', 'bot_started', 'bot_added'],
                        secret=secret,
                    )
                    if result.get('success'):
                        print('✓ Webhook зарегистрирован успешно')
                    else:
                        print(f'✗ Ошибка регистрации webhook: {result.get("message", "")}')
                except MAXAPIError as e:
                    print(f'✗ Ошибка регистрации webhook: {e}')

        # Проверка подключения
        try:
            bot_info = client.get_me()
            print('✓ Подключение к MAX API успешно')
            print(f'  Бот: {bot_info.get("first_name", "Unknown")}')
            print(f'  Username: @{bot_info.get("username", "N/A")}')
        except MAXAPIError as e:
            print(f'✗ Ошибка подключения: {e}')
            print('  Проверьте токен и доступность API.')

        print('')
        print('Бот запущен. Ожидание сообщений...')
        print('')
        sys.stdout.flush()

        try:
            marker = None
            last_heartbeat = time.time()
            while _running:
                try:
                    # Получаем обновления через Long Polling
                    result = client.get_updates(
                        limit=100,
                        timeout=30,
                        marker=marker,
                        types=['message_created', 'bot_started', 'bot_added'],
                    )

                    updates = result.get('updates', [])
                    marker = result.get('marker')

                    if updates:
                        for update in updates:
                            _process_update(
                                update, client, dry_run,
                                handle_command, handle_message, session_store,
                            )

                    # Heartbeat каждые 30 секунд
                    if time.time() - last_heartbeat > 30:
                        print(f'[{time.strftime("%H:%M:%S")}] Бот активен, marker={marker}')
                        sys.stdout.flush()
                        last_heartbeat = time.time()

                except MAXAPIError as e:
                    print(f'ERROR опроса: {e}')
                    sys.stdout.flush()
                    time.sleep(interval)
                except Exception as e:
                    print(f'ERROR: {e}')
                    import traceback
                    traceback.print_exc()
                    sys.stdout.flush()
                    time.sleep(interval)

                if not dry_run:
                    time.sleep(interval)

        except KeyboardInterrupt:
            print('')
            print('Бот остановлен пользователем.')
            print('')


def _process_update(update, client, dry_run, handle_command, handle_message, session_store):
    """Обработка одного обновления."""
    update_type = update.get('update_type', '')
    message_data = update.get('message', {})
    body_data = message_data.get('body', {})
    sender_data = message_data.get('sender', {})
    recipient_data = message_data.get('recipient', {})

    # user_id — кто отправил (sender)
    user_id = sender_data.get('user_id')
    if not user_id:
        return

    # Пропускаем события от ботов
    if sender_data.get('is_bot'):
        return

    # chat_id — куда отправлять ответ (recipient)
    chat_id = recipient_data.get('chat_id')

    # Текст сообщения
    message_text = body_data.get('text', '').strip()
    if not message_text:
        return

    username = sender_data.get('username', '') or sender_data.get('first_name', '')
    print(f'[{update_type}] {username} ({user_id}): {message_text}')
    sys.stdout.flush()

    # Обработка команд
    from messaging.bots.max_bot import BotResponse
    response = None
    if message_text.startswith('/'):
        parts = message_text.split(' ', 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ''
        response = handle_command(user_id, command, args)
    else:
        response = handle_message(user_id, message_text)

    if response:
        # Проверяем, является ли ответ BotResponse (с кнопками)
        if isinstance(response, BotResponse):
            text = response.text
            buttons = response.buttons
        else:
            text = str(response)
            buttons = []

        if dry_run:
            print(f'  → [DRY-RUN] Ответ:\n  {text[:200]}')
            if buttons:
                print(f'  → Кнопки: {buttons}')
        else:
            try:
                # Отправляем в чат/диалог (chat_id из recipient)
                if chat_id:
                    client.send_message(chat_id=chat_id, text=text, buttons=buttons)
                else:
                    client.send_message(user_id=user_id, text=text, buttons=buttons)
                print('  → Ответ отправлен')
            except MAXAPIError as e:
                print(f'  → Ошибка отправки: {e}')
        sys.stdout.flush()
