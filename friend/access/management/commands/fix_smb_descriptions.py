"""
Management command to fix SMB paths in resource descriptions.

Replaces ',/' with '/' in the description field of all resources.

Usage:
    python manage.py fix_smb_descriptions [--dry-run]
"""

from django.core.management.base import BaseCommand
from access.models import Resource


class Command(BaseCommand):
    help = 'Заменяет ",/" на "/" в поле description всех ресурсов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать изменения без сохранения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        count = 0
        updated = 0

        resources = Resource.objects.filter(description__contains=',/')

        self.stdout.write(f'Найдено ресурсов с ",/": {resources.count()}')

        for resource in resources:
            old_desc = resource.description
            new_desc = old_desc.replace(',/', '/')
            if old_desc != new_desc:
                count += 1
                self.stdout.write(
                    f'  #{resource.id} {resource.name}\n'
                    f'    Было: {old_desc}\n'
                    f'    Стало: {new_desc}'
                )
                if not dry_run:
                    resource.description = new_desc
                    resource.save(update_fields=['description', 'updated_at'])
                    updated += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDRY RUN — изменено записей: {count}. '
                    'Уберите --dry-run для применения.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nГотово. Обновлено записей: {updated}')
            )
