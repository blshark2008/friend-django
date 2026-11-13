"""
Management command to import network resources from CSV files.

Usage:
    python manage.py import_network_resources --file Users_Groups_common-media.csv
"""

import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from access.models import Resource, NetworkResourceDetail


def parse_smb_path(smb_url):
    """Распарсить smb://host/share в (host, share_path)."""
    match = re.match(r'^smb://([^/]+)/(.+)$', smb_url.strip())
    if not match:
        return None, None
    return match.group(1), match.group(2).rstrip(',').strip()


def parse_folder_line(line):
    """
    Парсит строку директории вида:
      Записи операций       D        0  Tue Feb 10 16,6,34 2026
      !Аппаратное               D        0  Wed Aug  5 13,3,02 2026
      "  !Семинары, конференции, уч.советы      D        0  Wed Aug  5 13",9,24 2026
    
    Возвращает имя папки или None.
    """
    # Убираем кавычки
    line = line.strip('"').strip("'")
    
    # Ищем паттерн: имя_папки пробелы D пробелы размер пробелы дата
    match = re.match(r'^\s+["\']?(.+?)["\']?\s+D\s+\d+\s+', line)
    if not match:
        return None
    name = match.group(1).strip()
    if not name:
        return None
    return name


class Command(BaseCommand):
    help = 'Импорт сетевых ресурсов из CSV файлов'

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
            raw_lines = f.readlines()

        # Объединяем строки, если первая начинается с кавычки (разбитый SMB путь)
        if raw_lines and raw_lines[0].strip().startswith('"'):
            # Собираем до закрывающей кавычки
            merged = raw_lines[0].rstrip('\n').rstrip('\r')
            idx = 1
            while idx < len(raw_lines):
                line = raw_lines[idx].rstrip('\n').rstrip('\r')
                merged += line
                if '"' in line:
                    break
                idx += 1
            # Извлекаем SMB путь из кавычек
            match = re.search(r'(smb://[^"]+)', merged)
            if match:
                smb_path = match.group(1).rstrip(',').strip()
            else:
                smb_path = merged.strip().strip('"').strip().rstrip(',').strip()
            lines = raw_lines[idx + 1:]
        else:
            smb_path = raw_lines[0].strip()
            lines = raw_lines[1:]

        host, share_path = parse_smb_path(smb_path)

        if not host:
            self.stdout.write(self.style.ERROR(f'Не удалось распарсить SMB путь: {smb_path}'))
            return

        self.stdout.write(f'SMB хост: {host}')
        self.stdout.write(f'Share path: {share_path}')

        if not lines:
            self.stdout.write(self.style.WARNING('Файл пуст'))
            return

        # Парсим папки
        folders = []
        for i, line in enumerate(lines, start=2):
            folder_name = parse_folder_line(line)
            if folder_name:
                folders.append(folder_name)

        self.stdout.write(f'Найдено папок: {len(folders)}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN — ничего не сохранено'))
            for f in folders:
                self.stdout.write(f'  - {f}')
            return

        # Создаём ресурсы
        created_resources = 0
        for folder_name in folders:
            resource_name = f'Network: {host}/{share_path}/{folder_name}'

            resource, created = Resource.objects.get_or_create(
                name=resource_name,
                defaults={
                    'type': Resource.Type.NETWORK,
                    'description': f'SMB share: {smb_path}/{folder_name}',
                    'is_active': True,
                },
            )
            if created:
                created_resources += 1
                self.stdout.write(self.style.SUCCESS(f'Создан: {resource_name}'))
            else:
                self.stdout.write(f'  Уже существует: {resource_name}')

            # Создаём/обновляем NetworkResourceDetail
            NetworkResourceDetail.objects.update_or_create(
                resource=resource,
                defaults={
                    'host': '0.0.0.0',
                    'share_path': f'smb://{host}/{share_path}/{folder_name}',
                    'protocol': 'smb',
                },
            )

        self.stdout.write(self.style.SUCCESS(f'\nГотово. Создано ресурсов: {created_resources}'))
