"""
Management command to import AD group names as AccessGroup records.

Usage:
    python manage.py import_ad_groups --file Users_Groups-только.csv
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from access.models import AccessGroup


class Command(BaseCommand):
    help = 'Импорт AD-групп из CSV файла как AccessGroup с old_name'

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

        # Создаём AccessGroup для каждой группы
        created = 0
        skipped = 0

        for group_name in groups:
            # Проверяем, существует ли уже группа с таким old_name
            if AccessGroup.objects.filter(old_name__iexact=group_name).exists():
                skipped += 1
                continue

            # Создаём новую группу
            try:
                AccessGroup.objects.create(
                    name=group_name,
                    old_name=group_name,
                    description=f'AD-группа: {group_name}',
                    is_active=True,
                )
                created += 1
                if created <= 10:
                    self.stdout.write(self.style.SUCCESS(f'Создана: {group_name}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка при создании {group_name}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nГотово. Создано: {created}, Пропущено (уже есть): {skipped}'))
