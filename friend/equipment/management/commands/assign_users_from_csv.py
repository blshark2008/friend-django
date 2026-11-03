import re
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from equipment.models import Computer, Laptop, Printer, PeripheralDevice, Phone

logger = logging.getLogger(__name__)
User = get_user_model()


def extract_name_from_mol(mol_str):
    """Извлекает ФИО из строки МОЛ.
    
    Примеры:
        'Лузанов А. К. - Отдел информационных технологий' -> 'Лузанов А. К.'
        'Краснобаева Ю. С. - Отдел экспериментальной...' -> 'Краснобаева Ю. С.'
    """
    if not mol_str or mol_str in ('<групповой учет>', '<не задан>', ''):
        return None
    
    # Extract name part (before " - ")
    parts = mol_str.split(' - ')
    if len(parts) >= 1:
        return parts[0].strip()
    return None


def find_user_by_name(name_part):
    """Ищет пользователя по части ФИО."""
    if not name_part:
        return None
    
    # Clean name
    name_part = name_part.strip()
    if not name_part or name_part == '<групповой учет>':
        return None
    
    # Try to extract last name (first word)
    words = name_part.split()
    if not words:
        return None
    
    last_name = words[0]
    
    # Try exact match on username
    try:
        user = User.objects.get(username__iexact=last_name)
        return user
    except User.DoesNotExist:
        pass
    
    # Try search in last_name field
    users = User.objects.filter(
        last_name__icontains=last_name
    ).filter(is_active=True)
    
    if users.count() == 1:
        return users.first()
    
    # Try search in first_name field
    if len(words) > 1:
        first_name = words[1]
        users = User.objects.filter(
            first_name__icontains=first_name
        ).filter(is_active=True)
        
        if users.count() == 1:
            return users.first()
    
    # Try search in full name
    full_search = f'{last_name}%'
    users = User.objects.filter(
        last_name__icontains=last_name
    ).filter(is_active=True)[:5]
    
    # Return best match if only one result
    if users.count() == 1:
        return users.first()
    
    return None


class Command(BaseCommand):
    help = 'Назначение пользователей на оборудование на основе данных из CSV (МОЛ)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', nargs='?', default='friend/os.csv',
                            help='Путь к CSV файлу')
        parser.add_argument('--dry-run', action='store_true',
                            help='Показать что будет назначено без сохранения')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options['dry_run']

        self.stdout.write(f'Читаю файл: {csv_file}')

        # Read CSV and build mapping: inventory_number -> mol
        mol_mapping = {}
        with open(csv_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Simple CSV parsing for our format
                # Format: Наименование,МОЛ/Место хранения,Инвентарный номер,...
                if 'Инвентарный номер' in line:
                    continue  # Skip header
                
                # Split by comma, but handle quoted fields
                parts = []
                current = ''
                in_quotes = False
                for char in line:
                    if char == '"':
                        in_quotes = not in_quotes
                    elif char == ',' and not in_quotes:
                        parts.append(current)
                        current = ''
                    else:
                        current += char
                parts.append(current)
                
                if len(parts) >= 3:
                    name = parts[0].strip().strip('"')
                    mol = parts[1].strip().strip('"')
                    inv_num = parts[2].strip().strip('"')
                    
                    if inv_num and inv_num not in ('<групповой учет>', '<не задано>', ''):
                        mol_mapping[inv_num] = mol

        self.stdout.write(f'Найдено записей с инв. номерами: {len(mol_mapping)}')

        # Find all equipment with inventory numbers
        equipment_models = [
            ('computer', Computer),
            ('laptop', Laptop),
            ('printer', Printer),
            ('peripheral', PeripheralDevice),
            ('phone', Phone),
        ]

        stats = {
            'processed': 0,
            'assigned': 0,
            'not_found_user': 0,
            'already_assigned': 0,
        }

        for eq_type, model in equipment_models:
            qs = model.objects.filter(
                inventory_number__in=mol_mapping.keys(),
                assigned_user__isnull=True,
                archived=False,
            )

            for item in qs:
                stats['processed'] += 1
                mol = mol_mapping.get(item.inventory_number, '')
                name_part = extract_name_from_mol(mol)
                
                if not name_part:
                    continue

                user = find_user_by_name(name_part)
                
                if user:
                    if dry_run:
                        self.stdout.write(
                            f'  [{eq_type}] INV:{item.inventory_number} | {item.name[:40]} | '
                            f'-> {user}'
                        )
                    else:
                        item.assigned_user = user
                        item.save()
                        stats['assigned'] += 1
                        self.stdout.write(
                            f'  Назначен: {user} -> {item.inventory_number} ({item.name[:40]})'
                        )
                else:
                    stats['not_found_user'] += 1

        # Print stats
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('РЕЗУЛЬТАТЫ')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Обработано:        {stats["processed"]}')
        self.stdout.write(f'Назначено:         {stats["assigned"]}')
        self.stdout.write(f'Пользователь не найден: {stats["not_found_user"]}')
        if dry_run:
            self.stdout.write(self.style.WARNING('Это был dry-run! Данные не сохранены.'))
        self.stdout.write('=' * 60)
