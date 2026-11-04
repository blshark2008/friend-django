import csv
import re
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'friend.settings')
django.setup()

from django.db.models import Q
from equipment.models import (
    Equipment, EquipmentCategory, Brand,
    EquipmentMovement,
)
from accounts.models import User


# ============================================================================
# Маппинг типов оборудования → (категория, подкатегория)
# ============================================================================
TYPE_TO_CATEGORY = {
    # Сетевое оборудование
    'GSM модем': ('Связь', 'GSM модем'),
    'HDMI-сплиттер': ('Сетевое оборудование', 'HDMI-сплиттер'),
    'IP-камера': ('Сетевое оборудование', 'IP-камера'),
    'SFP-модуль': ('Сетевое оборудование', 'SFP-модуль'),
    'WiFi контроллер': ('Сетевое оборудование', 'WiFi контроллер'),
    'WiFi точка': ('Сетевое оборудование', 'WiFi точка'),
    'WiFi-router': ('Сетевое оборудование', 'WiFi-router'),
    'Коммутатор (SWITCH)': ('Сетевое оборудование', 'Коммутатор (SWITCH)'),
    'Концентратор (HUB)': ('Сетевое оборудование', 'Концентратор (HUB)'),
    'Маршрутизатор': ('Сетевое оборудование', 'Маршрутизатор'),
    'Медиа-конвертер': ('Сетевое оборудование', 'Медиа-конвертер'),
    # Периферия
    'Веб-камера': ('Периферия', 'Веб-камера'),
    'Гарнитура (наушники)': ('Периферия', 'Гарнитура (наушники)'),
    'Звук.колонки': ('Периферия', 'Звук.колонки'),
    'Клавиатура': ('Периферия', 'Клавиатура'),
    'Монитор': ('Периферия', 'Монитор'),
    'Диктофон': ('Периферия', 'Диктофон'),
    'Жесткий диск': ('Периферия', 'Жесткий диск'),
    'Сумка под ноутбук': ('Периферия', 'Сумка под ноутбук'),
    'Лестница (стремянка)': ('Периферия', 'Лестница (стремянка)'),
    'Рутокен (электронный идентификатор)': ('Периферия', 'Рутокен (электронный идентификатор)'),
    'Сканер': ('Периферия', 'Сканер'),
    'Сканер штрих-кодов': ('Периферия', 'Сканер штрих-кодов'),
    'Шредер': ('Периферия', 'Шредер'),
    'Картридж ЦВ': ('Периферия', 'Картридж ЦВ'),
    # Компьютерное оборудование
    'Сист.блок': ('Компьютерное оборудование', 'Системный блок'),
    'Моноблок': ('Компьютерное оборудование', 'Моноблок'),
    'Ноутбук': ('Компьютерное оборудование', 'Ноутбук'),
    'Планшет': ('Компьютерное оборудование', 'Планшет'),
    'Тонкий клиент': ('Компьютерное оборудование', 'Тонкий клиент'),
    'Смарт-часы': ('Компьютерное оборудование', 'Смарт-часы'),
    'ТВ-приставки': ('Компьютерное оборудование', 'ТВ-приставка'),
    # Принтеры
    'Принтер лазерный ч/б': ('Принтеры', 'Принтер лазерный ч/б'),
    'Принтер лазерный цв.': ('Принтеры', 'Принтер лазерный цветной'),
    'МФУ лазерный': ('Принтеры', 'МФУ лазерный'),
    'МФУ струйный': ('Принтеры', 'МФУ струйный'),
    'Принтер струйный': ('Принтеры', 'Принтер струйный'),
    'Принтер этикеток': ('Принтеры', 'Принтер этикеток'),
    'Копиры, сканеры': ('Принтеры', 'Копиры, сканеры'),
    'Копировальный аппарат': ('Принтеры', 'Копиры, сканеры'),
    # Связь
    'Телефон VoIP': ('Связь', 'Телефон VoIP'),
    'Телефонный аппарат': ('Связь', 'Телефон VoIP'),
    'Телефон беспроводной (радиотелефон)': ('Связь', 'Телефон беспроводной (радиотелефон)'),
    'Телефон беспроводной 2 трубки': ('Связь', 'Телефон беспроводной 2 трубки'),
    'Телефон сотовый': ('Связь', 'Телефон сотовый'),
    'Факс': ('Связь', 'Факс'),
    'Системный телефон': ('Связь', 'Системный телефон'),
    'Терминал сбора данных': ('Связь', 'Терминал сбора данных'),
    # Видеооборудование
    'ВКС (видеоконференцсвязь)': ('Видеооборудование', 'ВКС (видеоконференцсвязь)'),
    'Проектор': ('Видеооборудование', 'Проектор'),
    'Телевизор': ('Видеооборудование', 'Телевизор'),
    'Фото-видео камера': ('Видеооборудование', 'Фото-видео камера'),
    'Яндекс-колонки': ('Периферия', 'Звук.колонки'),
    # Медицинское оборудование
    'Медицинское оборудование': ('Медицинское оборудование', 'Электрокардиограф'),
    'Электрокардиограф': ('Медицинское оборудование', 'Электрокардиограф'),
    # Прочее
    'ИБП': ('Сетевое оборудование', 'Коммутатор (SWITCH)'),
    'Дисковая стойка': ('Компьютерное оборудование', 'Системный блок'),
}


def parse_location(location_str):
    """Пытается распарсить строку местоположения."""
    if not location_str or location_str.strip() in ('-не указано-', '', 'Резерв', 'Резерв/НИИ'):
        return None, None, None, location_str.strip()

    parts = [p.strip() for p in location_str.split('/')]

    building_name = None
    floor_number = None
    room_number = None

    first = parts[0] if parts else ''

    corp_match = re.match(r'^Корпус\s*(\d+)', first, re.IGNORECASE)
    if corp_match:
        building_name = f"Корпус {corp_match.group(1)}"
        if len(parts) > 1:
            block_part = parts[1]
            block_match = re.match(r'^Блок\s*([А-ЯA-Z])\s*\(([^)]+)\)', block_part)
            if block_match:
                building_name = f"Корпус {corp_match.group(1)} — Блок {block_match.group(1)} ({block_match.group(2)})"
            else:
                building_name = f"Корпус {corp_match.group(1)} — {block_part}"

    if not corp_match:
        block_match = re.match(r'^Блок\s*([А-ЯA-Z])\s*\(([^)]+)\)', first)
        if block_match:
            building_name = f"Блок {block_match.group(1)} ({block_match.group(2)})"

    for i, part in enumerate(parts):
        fm = re.match(r'^(\d+)\s*этаж(?:\s*\(([^)]*)\))?', part, re.IGNORECASE)
        if fm:
            floor_number = int(fm.group(1))
            room_parts = parts[i + 1:]
            if room_parts:
                room_number = '/'.join(room_parts)
            break

    return building_name, floor_number, room_number, location_str.strip()


def find_user_by_name(name_str):
    """Ищет пользователя по ФИО."""
    if not name_str or name_str.strip() in ('-не указано-', '', 'НИИ', 'ККД'):
        return None

    name = name_str.strip()

    try:
        return User.objects.get(username__iexact=name)
    except (User.DoesNotExist, User.MultipleObjectsReturned):
        pass

    parts = name.split()
    if len(parts) >= 2:
        last_name = parts[0]
        first_name = parts[1]
        try:
            return User.objects.get(
                last_name__iexact=last_name,
                first_name__iexact=first_name,
            )
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            pass
    elif len(parts) == 1:
        try:
            return User.objects.get(last_name__iexact=parts[0])
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            pass

    return None


def get_or_create_brand(name):
    if not name or name.strip() == '':
        return None
    name = name.strip()
    brand, _ = Brand.objects.get_or_create(
        name__iexact=name,
        defaults={'name': name},
    )
    return brand


def get_category(name):
    try:
        return EquipmentCategory.objects.get(name=name, is_active=True)
    except EquipmentCategory.DoesNotExist:
        return None


def import_csv(filepath):
    created = 0
    skipped = 0
    errors = 0
    skipped_unknown_type = 0

    seen_inventory = {}

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f, delimiter=',')
        rows = list(reader)
        total = len(rows)

        print(f"Найдено {total} строк в CSV")
        print(f"Типов в маппинге: {len(TYPE_TO_CATEGORY)}")

        for i, row in enumerate(rows, 1):
            try:
                eq_type = row.get('Тип', '').strip()
                if not eq_type:
                    skipped += 1
                    continue

                if eq_type not in TYPE_TO_CATEGORY:
                    skipped_unknown_type += 1
                    skipped += 1
                    continue

                cat_name, sub_name = TYPE_TO_CATEGORY[eq_type]
                category = get_category(cat_name)
                subcategory = get_category(sub_name)

                if not category or not subcategory:
                    skipped += 1
                    continue

                inv_number = row.get('Инв номер', '').strip()
                if not inv_number or inv_number == '-':
                    skipped += 1
                    continue

                if inv_number in seen_inventory:
                    seen_inventory[inv_number] += 1
                    inv_number = f"{inv_number}_{seen_inventory[inv_number]}"
                else:
                    seen_inventory[inv_number] = 1

                serial = row.get('Серийный №', '').strip()
                name = row.get('Описание', '').strip()
                brand = get_or_create_brand(row.get('Производитель', ''))
                model = row.get('Модель', '').strip()

                acquisition_date_str = row.get('Дата пост', '').strip()
                acquisition_date = None
                if acquisition_date_str and acquisition_date_str != '-':
                    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
                        try:
                            from datetime import datetime
                            acquisition_date = datetime.strptime(acquisition_date_str, fmt).date()
                            break
                        except ValueError:
                            continue

                mol_name = row.get('МОЛ', '').strip()
                responsible_user = find_user_by_name(mol_name)

                user_name = row.get('Пользователь', '').strip()
                assigned_user = find_user_by_name(user_name)

                location_raw = row.get('Место', '').strip()
                location = ''
                if location_raw and location_raw != '-не указано-':
                    location = location_raw

                notes = row.get('Примечания', '').strip()
                extra_info = row.get('Доп.инф', '').strip()

                equipment = Equipment.objects.create(
                    inventory_number=inv_number,
                    serial_number=serial,
                    name=name,
                    brand=brand,
                    model=model,
                    category=category,
                    subcategory=subcategory,
                    assigned_user=assigned_user,
                    responsible_user=responsible_user,
                    location=location,
                    acquisition_date=acquisition_date,
                    status='active',
                    is_active=True,
                    archived=False,
                )

                mac_match = re.search(r'([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}', notes + ' ' + extra_info)
                if mac_match:
                    equipment.mac_address = mac_match.group(0).replace('-', ':')
                    equipment.save(update_fields=['mac_address'])

                if location:
                    EquipmentMovement.objects.create(
                        equipment=equipment,
                        from_location='Не указано',
                        to_location=location,
                        moved_by=responsible_user,
                        notes=f'Первичное размещение (импорт из CSV, строка {i})',
                    )

                created += 1
                if created % 500 == 0:
                    print(f"  Создано {created}/{total}...")

            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  [{i}/{total}] ОШИБКА: {e}")

    print(f"\n{'='*50}")
    print(f"Импорт завершён:")
    print(f"  Создано: {created}")
    print(f"  Пропущено (без инв. номера): {skipped}")
    print(f"  Пропущено (неизвестный тип): {skipped_unknown_type}")
    print(f"  Ошибки: {errors}")
    print(f"  Всего: {total}")
    print(f"  Уникальных инв. номеров: {len(seen_inventory)}")
    print(f"{'='*50}")


if __name__ == '__main__':
    import_csv('/home/user/projects/friend/eq_export.csv')
