# Generated data migration for equipment categories

from django.db import migrations


def create_categories(apps, schema_editor):
    """Создаёт иерархию категорий оборудования и маппит существующие записи."""
    EquipmentCategory = apps.get_model('equipment', 'EquipmentCategory')
    Equipment = apps.get_model('equipment', 'Equipment')

    # ========================================================================
    # Верхнеуровневые категории
    # ========================================================================
    top_categories = [
        ('Компьютерное оборудование', 'computer_top'),
        ('Принтеры', 'printers_top'),
        ('Периферия', 'periphery_top'),
        ('Сетевое оборудование', 'networking_top'),
        ('Связь', 'communication_top'),
        ('Медицинское оборудование', 'medical_top'),
        ('Видеооборудование', 'video_top'),
    ]

    top_map = {}
    for name, slug in top_categories:
        cat, _ = EquipmentCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'parent': None, 'is_active': True},
        )
        top_map[name] = cat

    # ========================================================================
    # Подкатегории компьютерного оборудования
    # ========================================================================
    computer_subs = [
        ('Компьютер', 'desktop'),
        ('Моноблок', 'monoblock'),
        ('Ноутбук', 'laptop'),
        ('Планшет', 'tablet'),
        ('Системный блок', 'system_unit'),
        ('Тонкий клиент', 'thin_client'),
        ('Сервер', 'server'),
        ('ТВ-приставка', 'tv_box'),
        ('Смарт-часы', 'smartwatch'),
    ]
    for name, slug in computer_subs:
        EquipmentCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'parent': top_map['Компьютерное оборудование'], 'is_active': True},
        )

    # ========================================================================
    # Подкатегории принтеров
    # ========================================================================
    printer_subs = [
        ('Принтер лазерный ч/б', 'laser_bw'),
        ('Принтер лазерный цветной', 'laser_color'),
        ('МФУ лазерный', 'mfp_laser'),
        ('МФУ струйный', 'mfp_inkjet'),
        ('Принтер струйный', 'inkjet'),
        ('Принтер этикеток', 'label_printer'),
        ('Копиры, сканеры', 'copiers_scanners'),
    ]
    for name, slug in printer_subs:
        EquipmentCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'parent': top_map['Принтеры'], 'is_active': True},
        )

    # ========================================================================
    # Подкатегории периферии
    # ========================================================================
    periphery_subs = [
        ('Гарнитура (наушники)', 'headset'),
        ('Звук.колонки', 'speakers'),
        ('Клавиатура', 'keyboard'),
        ('Монитор', 'monitor'),
        ('Веб-камера', 'webcam'),
        ('Диктофон', 'dictaphone'),
        ('Жесткий диск', 'hdd'),
        ('Сумка под ноутбук', 'laptop_bag'),
        ('Лестница (стремянка)', 'ladder'),
        ('Рутокен (электронный идентификатор)', 'rutoken'),
        ('Сканер', 'scanner'),
        ('Сканер штрих-кодов', 'barcode_scanner'),
        ('Шредер', 'shredder'),
    ]
    for name, slug in periphery_subs:
        EquipmentCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'parent': top_map['Периферия'], 'is_active': True},
        )

    # ========================================================================
    # Подкатегории сетевого оборудования
    # ========================================================================
    network_subs = [
        ('IP-камера', 'ip_camera'),
        ('SFP-модуль', 'sfp_module'),
        ('WiFi контроллер', 'wifi_controller'),
        ('WiFi точка', 'wifi_ap'),
        ('WiFi-router', 'wifi_router'),
        ('Коммутатор (SWITCH)', 'switch'),
        ('Концентратор (HUB)', 'hub'),
        ('Маршрутизатор', 'router'),
        ('Медиа-конвертер', 'media_converter'),
        ('HDMI-сплиттер', 'hdmi_splitter'),
    ]
    for name, slug in network_subs:
        EquipmentCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'parent': top_map['Сетевое оборудование'], 'is_active': True},
        )

    # ========================================================================
    # Подкатегории связи
    # ========================================================================
    communication_subs = [
        ('GSM модем', 'gsm_modem'),
        ('Телефон VoIP', 'voip_phone'),
        ('Системный телефон', 'system_phone'),
        ('Телефон беспроводной (радиотелефон)', 'cordless_phone'),
        ('Телефон беспроводной 2 трубки', 'cordless_phone_2'),
        ('Телефон сотовый', 'cellular_phone'),
        ('Факс', 'fax'),
        ('Терминал сбора данных', 'data_terminal'),
    ]
    for name, slug in communication_subs:
        EquipmentCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'parent': top_map['Связь'], 'is_active': True},
        )

    # ========================================================================
    # Подкатегории медицинского оборудования
    # ========================================================================
    medical_subs = [
        ('Электрокардиограф', 'ecg'),
    ]
    for name, slug in medical_subs:
        EquipmentCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'parent': top_map['Медицинское оборудование'], 'is_active': True},
        )

    # ========================================================================
    # Подкатегории видеооборудования
    # ========================================================================
    video_subs = [
        ('ВКС (видеоконференцсвязь)', 'vks'),
        ('Проектор', 'projector'),
        ('Телевизор', 'tv'),
        ('Фото-видео камера', 'photo_video_camera'),
    ]
    for name, slug in video_subs:
        EquipmentCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'parent': top_map['Видеооборудование'], 'is_active': True},
        )

    # ========================================================================
    # Маппинг старых значений category/subtype в новые категории
    # ========================================================================
    # Формат: (old_category_str, old_subtype_str) -> new_subcategory_name
    subtype_to_category = {
        # Компьютерное оборудование
        ('computer', 'desktop'): 'Компьютер',
        ('computer', 'monoblock'): 'Моноблок',
        ('computer', 'laptop'): 'Ноутбук',
        ('computer', 'tablet'): 'Планшет',
        ('computer', 'system_unit'): 'Системный блок',
        ('computer', 'monitor'): 'Монитор',
        ('computer', 'server'): 'Сервер',
        ('computer', 'thin_client'): 'Тонкий клиент',
        # Принтеры
        ('printer', 'laser_color'): 'Принтер лазерный цветной',
        ('printer', 'laser_bw'): 'Принтер лазерный ч/б',
        ('printer', 'mfp_laser'): 'МФУ лазерный',
        ('printer', 'mfp_inkjet'): 'МФУ струйный',
        # Периферия
        ('periphery', 'headset'): 'Гарнитура (наушники)',
        ('periphery', 'speakers'): 'Звук.колонки',
        # Прочее
        ('other', 'disk_array'): 'Дисковая стойка',
        ('other', 'vks'): 'ВКС (видеоконференцсвязь)',
    }

    # Обновляем существующие записи оборудования
    updated = 0
    for (old_cat_str, old_subtype_str), new_sub_name in subtype_to_category.items():
        Equipment.objects.filter(
            _category_str=old_cat_str,
            _subtype_str=old_subtype_str,
        ).update(
            category=top_map.get(old_cat_str),
            subcategory=EquipmentCategory.objects.filter(
                name=new_sub_name, is_active=True
            ).order_by().first(),
        )
        updated += 1

    print(f"Обновлено {updated} групп записей оборудования")


def delete_categories(apps, schema_editor):
    """Откат: удаляем созданные категории."""
    EquipmentCategory = apps.get_model('equipment', 'EquipmentCategory')
    EquipmentCategory.objects.filter(parent__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('equipment', '0006_add_equipment_category_model'),
    ]

    operations = [
        migrations.RunPython(create_categories, delete_categories),
    ]
