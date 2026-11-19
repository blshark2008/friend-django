"""
Management command: sync_ad_groups

Синхронизирует внутренние группы пользователей на основе AD-групп.

Использование:
    python manage.py sync_ad_groups [--user USERNAME] [--dry-run]

Опции:
    --user USERNAME   Синхронизировать только указанного пользователя
    --dry-run         Показать что будет сделано, без изменений
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from accounts.services import ADGroupSyncService

UserModel = get_user_model()


class Command(BaseCommand):
    help = 'Синхронизировать внутренние группы пользователей с AD'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user', type=str, default=None,
            help='Синхронизировать только указанного пользователя (по username)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Показать что будет сделано, без изменений',
        )

    def handle(self, *args, **options):
        user_filter = options['user']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('Режим dry-run: изменения не будут применены'))

        if user_filter:
            self.stdout.write(f'Синхронизация пользователя: {user_filter}')
            try:
                user = UserModel.objects.get(username=user_filter)
            except UserModel.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Пользователь {user_filter} не найден'))
                return

            result = ADGroupSyncService.sync_user_groups(user)
            self._print_result(user, result, dry_run)
        else:
            self.stdout.write('Массовая синхронизация всех пользователей...')
            result = ADGroupSyncService.sync_all_users()
            self.stdout.write(f'Всего: {result.get("total", 0)}')
            self.stdout.write(f'Успешно: {result.get("success", 0)}')
            self.stdout.write(f'Ошибки: {result.get("errors", 0)}')
            if result.get('last_sync'):
                self.stdout.write(f'Последняя синхронизация: {result["last_sync"]}')

    def _print_result(self, user, result, dry_run):
        prefix = '[DRY-RUN] ' if dry_run else ''

        if result['added']:
            for name in result['added']:
                self.stdout.write(
                    self.style.SUCCESS(f'{prefix}Добавлена группа: {name}')
                )
        if result['removed']:
            for name in result['removed']:
                self.stdout.write(
                    self.style.WARNING(f'{prefix}Удалена группа: {name}')
                )
        if result['errors']:
            for error in result['errors']:
                self.stdout.write(
                    self.style.ERROR(f'{prefix}Ошибка: {error}')
                )

        if not result['added'] and not result['removed'] and not result['errors']:
            self.stdout.write(f'{prefix}Группы пользователя {user} уже в актуальном состоянии')
