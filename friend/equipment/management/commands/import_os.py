import csv
import re
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models

from equipment.models import (
    Computer, Laptop, Printer, PeripheralDevice, Phone,
)

logger = logging.getLogger(__name__)
User = get_user_model()

# ============================================================================
# Классификация по названию
# ============================================================================

COMPUTER_PATTERNS = [
    r'компьютер',
    r'системн\.?блок',
    r'моноблок',
    r'арм\s*оператора',
    r'арм\s*инженер',
    r'арм\s*техн',
    r'арм\s*диспетч',
    r'арм\s*врач',
    r'стационарн\.?й',
    r'depo\s+neos',
    r'depo\s+race',
    r'hp\s+probook',
    r'hp\s+pro\s+book',
    r'lenovo',
    r'dell\s+precision',
    r'dell\s+optiplex',
    r'acer\s+verito',
]

LAPTOP_PATTERNS = [
    r'ноутбук',
    r'notebook',
    r'lap\s*top',
]

MONITOR_PATTERNS = [
    r'^\d+["\u00a2]\s*монитор',
    r'\bмонитор\b',
    r'видеомонитор',
]

# Negative patterns for monitors - exclude medical monitors
MONITOR_NEGATIVE_PATTERNS = [
    r'анестезиологическ',
    r'гемодинамическ',
    r'дефибриллятор',
    r'кардиологическ',
    r'суточн.*мониторирован',
    r'мониторирован.*экг',
    r'мониторирован.*ад',
    r'мониторинг.*мозгов',
    r'холтеровск',
    r'видеоэндоскоп',
    r'комплек.*мониторинг',
    r'клиническая анестезиология',
]

# Negative patterns for computers - exclude medical devices
COMPUTER_NEGATIVE_PATTERNS = [
    r'тренажер',
    r'реаним',
    r'эндоскоп',
]

PRINTER_PATTERNS = [
    r'\бпринтер\b',
    r'\бмфу\b',
    r'многофункциональн\.?е\s*устройств',
    r'копир',
    r'xerox\s+phaser',
    r'xerox\s+workcenter',
    r'xerox\s+b315',
    r'kyocera',
    r'hp\s+laserjet',
    r'hp\s+laser\s+jet',
    r'canon\s+imageRUNNER',
    r'canon\s+image\s+CLASS',
    r'ricoh',
    r'brother\s+mfc',
    r'lexmark',
    r'epson\s+l6',
    r'epson\s+l4',
]

CAMERA_PATTERNS = [
    r'\bip\s*-?\s*камер',
    r'\bip\s*-?\s*видеокамер',
    r'\bвеб\s*-?\s*камер',
    r'\bweb\s*-?\s*камер',
    r'\bвидеокамер',
    r'\bptz',
    r'hikvision',
    r'beward',
    r'praxis\s+pp',
    r'logitech\s+c920',
    r'sony\s+srg',
    r'sony\s+rm-ip',
    r'telycam',
    r'camera\s+web',
    r'video\s*камер',
]

# Negative patterns for cameras - exclude medical/lab chambers
CAMERA_NEGATIVE_PATTERNS = [
    r'гипоксийн',
    r'морозильн',
    r'холодильн',
    r'звукоизолирующ',
    r'электрофорезн',
    r'уф\s*камер',
    r'камера\s*для\s*разморажив',
    r'камера\s*для\s*вертикальн',
    r'камера\s*для\s*горизонтальн',
    r'камера\s*избыточн',
    r'камера\s*озонов',
    r'камера\s*греющ',
    r'камера\s*уф',
    r'мини-камер',
    r'камера\s*для\s*видеоконференц',
    r'камера\s*для\s*видеоконферен',
    r'источник\s*питания\s*для',
    r'камера\s*для\s*плазмы',
    r'камера\s*для\s*биоматериал',
    r'камера\s*для\s*электрофорез',
]

PHONE_PATTERNS = [
    r'\bip\s*-?\s*телефон',
    r'\bvoip\s*-?\s*телефон',
    r'\bsip\s*-?\s*телефон',
    r'\bтелефон\b',
    r'panasonic\s+kx',
    r'grandstream',
    r'cisco\s+ip',
]

SCANNER_PATTERNS = [
    r'\бсканер\b',
    r'blot\s*-?\s*сканер',
]

# 3D printers go to Printer model
PRINTER_3D_PATTERNS = [
    r'3\s*d\s*-?\s*принтер',
    r'3\s*d\s*принтер',
]


def classify_name(name):
    """Классифицирует оборудование по названию.
    
    Returns: (category, subcategory)
        category: 'computer', 'laptop', 'printer', 'peripheral_monitor', 
                  'peripheral_camera', 'peripheral_scanner', 'phone'
        subcategory: short description for logging
    """
    name_lower = name.lower().strip()
    
    # Remove leading special chars
    name_clean = re.sub(r'^[""\s!]+', '', name_lower)
    
    # Check laptops first (more specific)
    for pat in LAPTOP_PATTERNS:
        if re.search(pat, name_clean):
            return 'laptop', 'Ноутбук'
    
    # Check computers (with negative patterns)
    is_computer_negative = any(re.search(pat, name_clean) for pat in COMPUTER_NEGATIVE_PATTERNS)
    if not is_computer_negative:
        for pat in COMPUTER_PATTERNS:
            if re.search(pat, name_clean):
                return 'computer', 'Компьютер'
    
    # Check printers (including 3D)
    for pat in PRINTER_3D_PATTERNS:
        if re.search(pat, name_clean):
            return 'printer_3d', '3D-принтер'
    
    for pat in PRINTER_PATTERNS:
        if re.search(pat, name_clean):
            return 'printer', 'Принтер/МФУ'
    
    # Check scanners
    for pat in SCANNER_PATTERNS:
        if re.search(pat, name_clean):
            return 'peripheral_scanner', 'Сканер'
    
    # Check cameras (with negative patterns)
    is_camera_negative = any(re.search(pat, name_clean) for pat in CAMERA_NEGATIVE_PATTERNS)
    if not is_camera_negative:
        for pat in CAMERA_PATTERNS:
            if re.search(pat, name_clean):
                return 'peripheral_camera', 'Камера'
    
    # Check monitors (with negative patterns)
    is_monitor_negative = any(re.search(pat, name_clean) for pat in MONITOR_NEGATIVE_PATTERNS)
    if not is_monitor_negative:
        for pat in MONITOR_PATTERNS:
            if re.search(pat, name_clean):
                return 'peripheral_monitor', 'Монитор'
    
    # Check phones
    for pat in PHONE_PATTERNS:
        if re.search(pat, name_clean):
            return 'phone', 'Телефон'
    
    return None, None


def extract_brand_model(name):
    """Извлекает бренд и модель из названия.
    
    Examples:
        '27" Монитор Acer Vero CB271U' -> brand='Acer', model='Vero CB271U'
        'МФУ HP LaserJet Pro M428' -> brand='HP', model='LaserJet Pro M428'
        'Ноутбук F+ Flaptop i' -> brand='F+', model='Flaptop i'
    """
    # Known brands list (order matters - longer first)
    brands = [
        'asus', 'acer', 'lenovo', 'hp', 'hewlett-packard', 'dell',
        'ibm', 'apple', 'samsung', 'lg', 'sony', 'fujitsu', 'toshiba',
        'kyocera', 'canon', 'ricoh', 'xerox', 'brother', 'epson',
        'lexmark', 'viewsonic', 'iiyama', 'msi', 'depco', 'depo',
        'logitech', 'microsoft', 'praxis', 'beward', 'hikvision',
        'grandstream', 'panasonic', 'anycubic', 'creabot', 'formlabs',
        'greality', 'greal', 'sherpa', 'efficia', 'аксион', 'axon',
    ]
    
    # Remove common prefixes and noise
    cleaned = re.sub(r'^[""\s!]+', '', name.strip())
    cleaned = re.sub(r'^\d+["\u00a2]\s*', '', cleaned)  # Remove "27" prefix
    
    # Try to find brand in name
    brand = ''
    model = cleaned
    
    for br in sorted(brands, key=len, reverse=True):
        pattern = r'\b' + br + r'\b'
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            brand = match.group(0).title()
            # Model is everything after brand
            idx = match.end()
            if idx < len(cleaned):
                model = cleaned[idx:].strip().lstrip(',. ')
            else:
                model = ''
            break
    
    return brand, model


def extract_mol_user(mol_str):
    """Пытается найти пользователя по строке MOL.
    
    Example: 'Лузанов А. К. - Отдел информационных технологий'
    """
    if not mol_str or mol_str in ('<групповой учет>', '<не задан>', ''):
        return None
    
    # Extract name part (before " - ")
    parts = mol_str.split(' - ')
    if len(parts) >= 1:
        name_part = parts[0].strip()
        # Try to find user by name
        try:
            # Try exact first.last match
            users = User.objects.filter(
                models.Q(first_name__icontains=name_part) |
                models.Q(last_name__icontains=name_part) |
                models.Q(username__icontains=name_part) |
                models.Q(email__icontains=name_part)
            )
            if users.count() == 1:
                return users.first()
        except Exception:
            pass
    
    return None


class Command(BaseCommand):
    help = 'Импорт оборудования из CSV выкладки ОС'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', nargs='?', default='friend/os.csv',
                            help='Путь к CSV файлу')
        parser.add_argument('--dry-run', action='store_true',
                            help='Показать что будет загружено без сохранения')
        parser.add_argument('--force', action='store_true',
                            help='Перезаписать существующие записи')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options['dry_run']
        force = options['force']

        self.stdout.write(f'Читаю файл: {csv_file}')

        # Read CSV
        rows = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        self.stdout.write(f'Всего строк в CSV: {len(rows)}')

        # Statistics
        stats = {
            'total': 0,
            'skipped_no_inv': 0,
            'skipped_group': 0,
            'classified': {},
            'created': {},
            'updated': {},
            'errors': 0,
            'skipped_unknown': 0,
        }

        seen_inventory = set()

        for row in rows:
            stats['total'] += 1
            
            # Get inventory number
            inv_num = row.get('Инвентарный номер', '').strip()
            
            # Skip if no inventory number
            if not inv_num or inv_num in ('<групповой учет>', '<не задано>', ''):
                stats['skipped_no_inv'] += 1
                continue
            
            # Skip if already seen (should be unique)
            if inv_num in seen_inventory:
                continue
            seen_inventory.add(inv_num)

            # Get name
            name = row.get('Наименование', '').strip()
            if not name:
                stats['skipped_no_inv'] += 1
                continue

            # Classify
            category, subcategory = classify_name(name)
            
            if category is None:
                stats['skipped_unknown'] += 1
                continue

            stats['classified'][subcategory] = stats['classified'].get(subcategory, 0) + 1

            # Get other fields
            serial = row.get('Заводской номер', '').strip()
            mol = row.get('МОЛ/Место хранения', '').strip()
            
            # Extract brand/model
            brand, model = extract_brand_model(name)

            if dry_run:
                self.stdout.write(
                    f'  [{subcategory}] INV:{inv_num} | {name[:80]} | MOL:{mol[:40]} | SN:{serial[:20]}'
                )
                continue

            # Import based on category
            try:
                if category == 'computer':
                    obj, created = Computer.objects.update_or_create(
                        inventory_number=inv_num,
                        defaults={
                            'serial_number': serial,
                            'name': name,
                            'brand': brand,
                            'model': model,
                        }
                    )
                    key = 'computer'
                
                elif category == 'laptop':
                    obj, created = Laptop.objects.update_or_create(
                        inventory_number=inv_num,
                        defaults={
                            'serial_number': serial,
                            'name': name,
                            'brand': brand,
                            'model': model,
                        }
                    )
                    key = 'laptop'
                
                elif category in ('printer', 'printer_3d'):
                    obj, created = Printer.objects.update_or_create(
                        inventory_number=inv_num,
                        defaults={
                            'serial_number': serial,
                            'name': name,
                            'brand': brand,
                            'model': model,
                        }
                    )
                    key = 'printer'
                
                elif category == 'peripheral_monitor':
                    obj, created = PeripheralDevice.objects.update_or_create(
                        inventory_number=inv_num,
                        defaults={
                            'name': name,
                            'device_type': 'monitor',
                            'brand': brand,
                            'model': model,
                        }
                    )
                    key = 'monitor'
                
                elif category == 'peripheral_camera':
                    obj, created = PeripheralDevice.objects.update_or_create(
                        inventory_number=inv_num,
                        defaults={
                            'name': name,
                            'device_type': 'camera',
                            'brand': brand,
                            'model': model,
                        }
                    )
                    key = 'camera'
                
                elif category == 'peripheral_scanner':
                    obj, created = PeripheralDevice.objects.update_or_create(
                        inventory_number=inv_num,
                        defaults={
                            'name': name,
                            'device_type': 'scanner',
                            'brand': brand,
                            'model': model,
                        }
                    )
                    key = 'scanner'
                
                elif category == 'phone':
                    obj, created = Phone.objects.update_or_create(
                        inventory_number=inv_num,
                        defaults={
                            'name': name,
                            'brand': brand,
                            'model': model,
                        }
                    )
                    key = 'phone'
                
                else:
                    stats['skipped_unknown'] += 1
                    continue

                if created:
                    stats['created'][key] = stats['created'].get(key, 0) + 1
                else:
                    stats['updated'][key] = stats['updated'].get(key, 0) + 1

            except (IntegrityError, Exception) as e:
                stats['errors'] += 1
                logger.error(f'Error processing {inv_num}: {e}')

        # Print stats
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('РЕЗУЛЬТАТЫ ИМПОРТА')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Всего строк:         {stats["total"]}')
        self.stdout.write(f'Без инв. номера:     {stats["skipped_no_inv"]}')
        self.stdout.write(f'Не классифицировано: {stats["skipped_unknown"]}')
        self.stdout.write(f'Ошибки:              {stats["errors"]}')
        self.stdout.write(f'\nКлассификация:')
        for cat, count in sorted(stats['classified'].items()):
            self.stdout.write(f'  {cat:25s} {count:6d}')
        self.stdout.write(f'\nСоздано:')
        for cat, count in sorted(stats['created'].items()):
            self.stdout.write(f'  {cat:25s} {count:6d}')
        self.stdout.write(f'\nОбновлено:')
        for cat, count in sorted(stats['updated'].items()):
            self.stdout.write(f'  {cat:25s} {count:6d}')
        self.stdout.write('=' * 60)

        if dry_run:
            self.stdout.write(self.style.WARNING('Это был dry-run! Данные не сохранены.'))
