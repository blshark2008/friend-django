from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType
from django.contrib.contenttypes.models import ContentType as CT
from accounts.models import MenuSection, MenuItem


class Command(BaseCommand):
    help = 'Создаёт разделы и пункты меню с правами доступа'

    def handle(self, *args, **options):
        # Разделы меню с их пунктами
        menu_structure = [
            {
                'name': 'Сотрудники',
                'code': 'employees',
                'icon': 'bi-people',
                'items': [
                    {'name': 'Список пользователей', 'url_name': 'accounts:user_list', 'icon': 'bi-list-ul'},
                    {'name': 'Список подразделений', 'url_name': 'accounts:department_list', 'icon': 'bi-building'},
                    {'name': 'Список должностей', 'url_name': 'accounts:position_list', 'icon': 'bi-briefcase'},
                ]
            },
            {
                'name': 'Обучение',
                'code': 'training',
                'icon': 'bi-mortarboard',
                'items': [
                    {'name': 'Обучающие курсы', 'url_name': 'training:type_list', 'icon': 'bi-book'},
                    {'name': 'Журнал обучения', 'url_name': 'training:journal', 'icon': 'bi-journal-text'},
                    {'name': 'Цели обучения', 'url_name': 'training:goal_list', 'icon': 'bi-bullseye'},
                ]
            },
            {
                'name': 'Подразделения',
                'code': 'departments',
                'icon': 'bi-building',
                'items': [
                    {'name': 'Список подразделений', 'url_name': 'accounts:department_list', 'icon': 'bi-building'},
                ]
            },
            {
                'name': 'Сообщения',
                'code': 'messaging',
                'icon': 'bi-envelope-fill',
                'items': [
                    {'name': 'Все сообщения', 'url_name': 'messaging:message_list', 'icon': 'bi-envelope'},
                    {'name': 'Новое сообщение', 'url_name': 'messaging:message_create', 'icon': 'bi-pencil-square'},
                    {'name': 'Статистика', 'url_name': 'messaging:message_stats', 'icon': 'bi-bar-chart'},
                ]
            },
            {
                'name': 'Сценарии оповещений',
                'code': 'scenarios',
                'icon': 'bi-diagram-3',
                'items': [
                    {'name': 'Все сценарии', 'url_name': 'scenarios:scenario_list', 'icon': 'bi-file-earmark'},
                    {'name': 'Запуски', 'url_name': 'scenarios:run_list', 'icon': 'bi-play-circle'},
                    {'name': 'Журнал', 'url_name': 'scenarios:journal_list', 'icon': 'bi-journal-text'},
                    {'name': 'Категории', 'url_name': 'scenarios:category_list', 'icon': 'bi-folder'},
                    {'name': 'Роли', 'url_name': 'scenarios:role_list', 'icon': 'bi-people'},
                ]
            },
            {
                'name': 'Доступы',
                'code': 'access',
                'icon': 'bi-shield-lock',
                'items': [
                    {'name': 'Роли', 'url_name': 'access:role_list', 'icon': 'bi-person-badge'},
                    {'name': 'Группы доступа', 'url_name': 'access:group_list', 'icon': 'bi-collection'},
                    {'name': 'Гранты доступа', 'url_name': 'access:grant_list', 'icon': 'bi-key'},
                    {'name': 'Заявки на доступ', 'url_name': 'access:request_list', 'icon': 'bi-inbox'},
                    {'name': 'Контейнеры групп', 'url_name': 'access:container_list', 'icon': 'bi-folder-symlink'},
                    {'name': 'Роли должностей', 'url_name': 'access:position_roles', 'icon': 'bi-briefcase'},
                    {'name': 'Аудит доступа', 'url_name': 'access:audit', 'icon': 'bi-shield-check'},
                ]
            },
            {
                'name': 'Права доступа',
                'code': 'internal_groups',
                'icon': 'bi-shield-lock',
                'items': [
                    {'name': 'Внутренние группы', 'url_name': 'accounts:internal_group_list', 'icon': 'bi-shield-lock'},
                    {'name': 'Связки AD-групп', 'url_name': 'accounts:group_mapping_list', 'icon': 'bi-link-45deg'},
                ]
            },
            {
                'name': 'Оборудование',
                'code': 'equipment',
                'icon': 'bi-pc-display',
                'items': [
                    {'name': 'Всё оборудование', 'url_name': 'equipment:equipment_list', 'icon': 'bi-list-ul'},
                    {'name': 'Дашборд', 'url_name': 'equipment:dashboard', 'icon': 'bi-speedometer2'},
                    {'name': 'Экспорт в Excel', 'url_name': 'equipment:export_excel', 'icon': 'bi-file-earmark-excel'},
                    {'name': 'Компьютеры', 'url_name': 'equipment:computers', 'icon': 'bi-pc-display'},
                    {'name': 'Ноутбуки', 'url_name': 'equipment:computers', 'icon': 'bi-laptop'},
                    {'name': 'Принтеры/МФУ', 'url_name': 'equipment:printers', 'icon': 'bi-printer'},
                    {'name': 'Медицинское', 'url_name': 'equipment:medical', 'icon': 'bi-heart-pulse'},
                    {'name': 'Периферия', 'url_name': 'equipment:peripherals', 'icon': 'bi-display'},
                    {'name': 'Телефоны', 'url_name': 'equipment:phones', 'icon': 'bi-telephone'},
                    {'name': 'ВКС', 'url_name': 'equipment:vks', 'icon': 'bi-camera-video'},
                    {'name': 'Инвентаризация', 'url_name': 'equipment:inventory', 'icon': 'bi-clipboard-check'},
                    {'name': 'Закрепленное', 'url_name': 'equipment:assigned_equipment', 'icon': 'bi-person-check'},
                    {'name': 'Загрузка ОС', 'url_name': 'equipment:upload_os', 'icon': 'bi-cloud-upload'},
                    {'name': 'Справочник категорий', 'url_name': 'equipment:categories_reference', 'icon': 'bi-book'},
                    {'name': 'Справочник исключений', 'url_name': 'equipment:exclude_keywords_reference', 'icon': 'bi-list-x'},
                    {'name': 'Ключевые слова', 'url_name': 'equipment:filter_keywords_reference', 'icon': 'bi-tags'},
                    {'name': 'Настройки полей', 'url_name': 'equipment:field_settings', 'icon': 'bi-sliders'},
                    {'name': 'Справочник расположения', 'url_name': 'equipment:location_list', 'icon': 'bi-geo-alt'},
                    {'name': 'Управление категориями', 'url_name': 'equipment:category_list', 'icon': 'bi-folder2-open'},
                ]
            },
            {
                'name': 'Безопасность',
                'code': 'security',
                'icon': 'bi-shield-check',
                'items': [
                    {'name': 'SIEM дашборд', 'url_name': 'siem:dashboard', 'icon': 'bi-grid-1x2'},
                    {'name': 'Хосты', 'url_name': 'siem:hosts', 'icon': 'bi-pc-display'},
                    {'name': 'События', 'url_name': 'siem:events', 'icon': 'bi-list-ul'},
                    {'name': 'Алерты', 'url_name': 'siem:alerts_list', 'icon': 'bi-bell'},
                    {'name': 'Журнал блокировок', 'url_name': 'siem:screen_lock_log', 'icon': 'bi-lock-fill'},
                    {'name': 'История входов', 'url_name': 'siem:login_history', 'icon': 'bi-box-arrow-in-right'},
                    {'name': 'Заявки на отключение', 'url_name': 'siem:leaves_list', 'icon': 'bi-calendar-x'},
                    {'name': 'Отчёты', 'url_name': 'siem:report_security', 'icon': 'bi-file-earmark-bar'},
                    {'name': 'Помощь', 'url_name': 'siem:help', 'icon': 'bi-question-circle'},
                ]
            },
            {
                'name': 'Настройки',
                'code': 'settings',
                'icon': 'bi-gear',
                'items': [
                    {'name': 'Настройка меню', 'url_name': 'accounts:menu_settings', 'icon': 'bi-list-nested'},
                    {'name': 'Админ-панель', 'url_pattern': '/admin/', 'icon': 'bi-gear-wide'},
                ]
            },
        ]

        created_sections = 0
        created_items = 0

        for section_data in menu_structure:
            section, created = MenuSection.objects.get_or_create(
                code=section_data['code'],
                defaults={
                    'name': section_data['name'],
                    'icon': section_data['icon'],
                    'description': f'Раздел меню: {section_data["name"]}',
                }
            )
            if created:
                created_sections += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Создан раздел: {section.name}'))
            else:
                section.name = section_data['name']
                section.icon = section_data['icon']
                section.save()

            # Создаём пункты меню
            for item_data in section_data['items']:
                MenuItem.objects.get_or_create(
                    section=section,
                    url_name=item_data.get('url_name', ''),
                    defaults={
                        'name': item_data['name'],
                        'url_pattern': item_data.get('url_pattern', ''),
                        'icon': item_data.get('icon', ''),
                        'order': section_data['items'].index(item_data),
                        'is_active': True,
                    }
                )
                created_items += 1

        # Создаём права для каждого раздела
        for section in MenuSection.objects.filter(is_active=True):
            # Проверяем, есть ли уже ContentType для MenuSection
            ct, _ = CT.objects.get_or_create(
                app_label='accounts',
                model='menusection'
            )

            # Создаём права: view, change, add, delete
            for codename in ['view_menusection', 'change_menusection', 'add_menusection', 'delete_menusection']:
                perm, created = Permission.objects.get_or_create(
                    codename=codename,
                    defaults={
                        'name': f'Can {codename.replace("_", " ")} {section.name}',
                        'content_type': ct,
                    }
                )
                if created:
                    self.stdout.write(f'  ✓ Создано право: {codename}')

        # Создаём права для MenuItem
        menu_item_ct, _ = CT.objects.get_or_create(
            app_label='accounts',
            model='menuitem'
        )
        for codename in ['view_menuitem', 'change_menuitem', 'add_menuitem', 'delete_menuitem']:
            Permission.objects.get_or_create(
                codename=codename,
                defaults={
                    'name': f'Can {codename.replace("_", " ")} menu item',
                    'content_type': menu_item_ct,
                }
            )

        self.stdout.write(self.style.SUCCESS(f'\nГотово! Создано разделов: {created_sections}, пунктов меню: {created_items}'))
