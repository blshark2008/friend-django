"""
Команда тестирования подключения к MAX API.

Запуск:
    python manage.py testmaxapi
"""

import sys
import logging

from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Тестирование подключения к MAX API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            default=None,
            help='Токен MAX-бота',
        )

    def handle(self, *args, **options):
        token = options['token'] or getattr(settings, 'MAX_BOT_TOKEN', '')
        base_url = getattr(settings, 'MAX_API_BASE_URL', 'https://platform-api2.max.ru')

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  Тестирование MAX API'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'  Токен: {token[:10]}...{token[-5:] if len(token) > 15 else ""}')
        self.stdout.write(f'  URL: {base_url}')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')

        if not token:
            self.stdout.write(
                self.style.ERROR('Ошибка: токен не настроен в settings.py')
            )
            sys.exit(1)

        try:
            from messaging.services.max_api import MAXClient, MAXAPIError
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'Ошибка импорта: {e}'))
            sys.exit(1)

        try:
            client = MAXClient(token, base_url)
        except MAXAPIError as e:
            self.stdout.write(self.style.ERROR(f'Ошибка инициализации: {e}'))
            sys.exit(1)

        # Тест 1: Проверка подключения (GET /me)
        self.stdout.write('[1/4] Проверка подключения (GET /me)...')
        try:
            bot_info = client.get_me()
            self.stdout.write(self.style.SUCCESS('  ✓ Подключение успешно'))
            self.stdout.write(f'    Бот: {bot_info.get("first_name", "Unknown")}')
            self.stdout.write(f'    Username: @{bot_info.get("username", "N/A")}')
            self.stdout.write(f'    is_bot: {bot_info.get("is_bot", False)}')
        except MAXAPIError as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Ошибка: {e}'))

        # Тест 2: Long Polling (GET /updates)
        self.stdout.write('')
        self.stdout.write('[2/4] Проверка Long Polling (GET /updates)...')
        try:
            result = client.get_updates(limit=1, timeout=1)
            updates = result.get('updates', [])
            marker = result.get('marker')
            self.stdout.write(self.style.SUCCESS(f'  ✓ Получено {len(updates)} обновлений'))
            if marker:
                self.stdout.write(f'    Marker: {marker}')
        except MAXAPIError as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Ошибка: {e}'))

        # Тест 3: Отправка сообщения
        self.stdout.write('')
        self.stdout.write('[3/4] Проверка отправки сообщения (POST /messages)...')
        self.stdout.write('  ℹ Требуется user_id или chat_id для реальной отправки')
        self.stdout.write('  ℹ Для теста отправьте /start боту в MAX')

        # Тест 4: Проверка базы данных
        self.stdout.write('')
        self.stdout.write('[4/4] Проверка базы данных...')
        try:
            from accounts.models import User
            count = User.objects.count()
            with_max = User.objects.filter(notify_max=True).count()
            with_telegram = User.objects.filter(notify_telegram=True).count()
            with_email = User.objects.filter(
                notify_corporate_email=True
            ).count()
            self.stdout.write(self.style.SUCCESS(f'  ✓ Пользователей в БД: {count}'))
            self.stdout.write(f'    С MAX: {with_max}')
            self.stdout.write(f'    С Telegram: {with_telegram}')
            self.stdout.write(f'    С Email: {with_email}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Ошибка: {e}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  Тестирование завершено'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        self.stdout.write('Рекомендации:')
        self.stdout.write('  1. Убедитесь, что бот добавлен в MAX')
        self.stdout.write('  2. Для production настройте Webhook:')
        self.stdout.write('     python manage.py runmaxbot --subscribe')
        self.stdout.write('  3. Установите MAX_WEBHOOK_URL в settings.py')
