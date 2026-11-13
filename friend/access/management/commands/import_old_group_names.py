"""
Management command to import old group names from CSV file.

Usage:
    python manage.py import_old_group_names --file Users_Groups-только.csv
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from access.models import AccessGroup


class Command(BaseCommand):
    help = 'Импорт старых наименований групп из CSV файла'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Путь к CSV файлу (относительно проекта или абсолютный)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано, но не сохранять',
        )

    def handle(self, *args, **options):
        file_path = options.get('file')
        dry_run = options.get('dry_run')

        if not file_path:
            self.stdout.write(self.style.ERROR('Укажите --file'))
            return

        # Определяем путь к файлу
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        csv_file = Path(file_path)
        if not csv_file.is_absolute():
            csv_file = project_root / csv_file

        if not csv_file.exists():
            self.stdout.write(self.style.ERROR(f'Файл не найден: {csv_file}'))
            return

        self.stdout.write(f'Чтение файла: {csv_file}')

        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            self.stdout.write(self.style.WARNING('Файл пуст'))
            return

        # Первая строка — заголовок (SecurityGroups)
        groups = []
        for line in lines[1:]:
            name = line.strip().strip('"').strip()
            if name:
                groups.append(name)

        self.stdout.write(f'Найдено групп: {len(groups)}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN — ничего не сохранено'))
            for i, g in enumerate(groups[:20]):
                self.stdout.write(f'  {i+1}. {g}')
            if len(groups) > 20:
                self.stdout.write(f'  ... и ещё {len(groups) - 20}')
            return

        # Обновляем old_name у существующих групп
        updated = 0
        not_found = 0

        for group_name in groups:
            # Ищем группу по old_name (case-insensitive)
            try:
                group = AccessGroup.objects.get(old_name__iexact=group_name)
                # Обновляем old_name
                group.old_name = group_name
                if not dry_run:
                    group.save(update_fields=['old_name'])
                updated += 1
                self.stdout.write(self.style.SUCCESS(f'Обновлено: {group_name} -> {group.name}'))
            except AccessGroup.DoesNotExist:
                not_found += 1

        self.stdout.write(self.style.SUCCESS(f'\nГотово. Обновлено: {updated}, Не найдено: {not_found}'))
