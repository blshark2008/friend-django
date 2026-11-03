import csv
import re
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts.models import User, Department, Position


def parse_name(full_name):
    """Разбирает 'Фамилия Имя Отчество (примечание)' на части."""
    # Убираем примечание в скобках: (внеш), (врем), (вн), (вн реаб) и т.д.
    name = re.sub(r'\s*\(.*?\)', '', full_name).strip()
    parts = name.split()
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        return parts[0], parts[1], ''
    elif len(parts) == 1:
        return parts[0], '', ''
    return '', '', ''


def clean_tab_number(tab):
    """Убирает пробелы из табельного номера."""
    return tab.strip().replace(' ', '')


def normalize_name(name):
    """Нормализует имя для поиска."""
    return re.sub(r'\s+', ' ', name.strip().lower())


class Command(BaseCommand):
    help = 'Импорт сотрудников из CSV (СотрудникиПочты.csv)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV-файлу')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        self.stdout.write(f'Читаю файл: {csv_file}')

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f'Файл не найден: {csv_file}')
        except Exception as e:
            raise CommandError(f'Ошибка чтения файла: {e}')

        if not rows:
            raise CommandError('Файл пустой')

        header = [c.strip() for c in rows[0]]
        self.stdout.write(f'Заголовок: {header}')

        created_users = 0
        updated_users = 0
        updated_tab_only = 0
        created_departments = 0
        created_positions = 0
        skipped_rows = 0

        for i, row in enumerate(rows[1:], start=2):
            row = [c.strip() for c in row]
            if not any(row):
                continue

            if len(row) < 2:
                skipped_rows += 1
                continue

            employee_name = row[0]       # Сотрудник
            tab_number = clean_tab_number(row[1]) if len(row) > 1 else ''  # Табельный номер
            position_name = row[2] if len(row) > 2 else ''  # Должность
            department_name = row[3] if len(row) > 3 else ''  # Подразделение
            email = row[4].strip() if len(row) > 4 else ''  # Email

            if not employee_name:
                skipped_rows += 1
                continue

            # Разбираем ФИО (убираем примечания вроде "(внеш)", "(врем)")
            last_name, first_name, patronymic = parse_name(employee_name)

            if not last_name:
                skipped_rows += 1
                continue

            # Создаём/находим подразделение
            department = None
            if department_name:
                department, dept_created = Department.objects.get_or_create(
                    name=department_name,
                )
                if dept_created:
                    created_departments += 1

            # Создаём/находим должность
            position = None
            if position_name:
                position, pos_created = Position.objects.get_or_create(
                    name=position_name,
                )
                if pos_created:
                    created_positions += 1
                # Привязываем должность к подразделению
                if department and position.department_id != department.pk:
                    position.department = department
                    position.save(update_fields=['department'])

            # Ищем пользователя
            user = None

            # 1. По табельному номеру (уникальный ключ)
            if tab_number:
                try:
                    user = User.objects.get(tab_number=tab_number)
                except User.DoesNotExist:
                    pass

            # 2. По email (filter вместо get — может быть несколько с одним email)
            if not user and email:
                users_with_email = User.objects.filter(email=email)
                if users_with_email.exists():
                    # Если один — берём его
                    if users_with_email.count() == 1:
                        user = users_with_email.first()
                    else:
                        # Если несколько — ищем совпадение по ФИО среди них
                        norm_last = normalize_name(last_name)
                        norm_first = normalize_name(first_name)
                        for u in users_with_email:
                            u_parts = normalize_name(u.last_name), normalize_name(u.first_name)
                            if norm_last == u_parts[0] and norm_first == u_parts[1]:
                                user = u
                                break
                        # Если не нашли по ФИО — берём первого
                        if not user:
                            user = users_with_email.first()

            # 3. По username (фамилия)
            if not user:
                username_guess = last_name.lower()
                try:
                    user = User.objects.get(username=username_guess)
                except User.DoesNotExist:
                    pass

            # 4. По ФИО (перебор)
            if not user:
                norm_last = normalize_name(last_name)
                norm_first = normalize_name(first_name)

                for u in User.objects.all():
                    u_parts = normalize_name(u.last_name), normalize_name(u.first_name)
                    if norm_last == u_parts[0] and norm_first == u_parts[1]:
                        user = u
                        break

            if user:
                # Обновляем существующего
                changes = []

                if tab_number and user.tab_number != tab_number:
                    user.tab_number = tab_number
                    changes.append(f'табель: {user.tab_number}')

                if email and user.corporate_email != email:
                    user.corporate_email = email
                    changes.append(f'email: {email}')

                if department and user.department_id != department.pk:
                    user.department = department
                    changes.append(f'подразделение: {department.name}')

                if position and user.position_id != position.pk:
                    user.position = position
                    changes.append(f'должность: {position.name}')

                if changes:
                    update_fields = ['tab_number', 'corporate_email', 'department', 'position']
                    user.save(update_fields=update_fields)
                    updated_users += 1
                    self.stdout.write(
                        f'  Обновлён: {employee_name} → {", ".join(changes)}',
                        self.style.WARNING
                    )
                else:
                    updated_tab_only += 1

            else:
                # Создаём нового пользователя
                username = last_name.lower()
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f'{base_username}{counter}'
                    counter += 1

                User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    patronymic=patronymic,
                    email=email,
                    tab_number=tab_number,
                    department=department,
                    position=position,
                    password='temp12345',  # временный пароль
                )
                created_users += 1
                self.stdout.write(
                    f'  Создан: {employee_name} → {department_name or "?"} / {position_name or "?"}',
                    self.style.SUCCESS
                )

        # Итоги
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('ИТОГИ ИМПОРТА:'))
        self.stdout.write(self.style.SUCCESS(f'  Подразделений создано:  {created_departments}'))
        self.stdout.write(self.style.SUCCESS(f'  Должностей создано:    {created_positions}'))
        self.stdout.write(self.style.SUCCESS(f'  Пользователей создано: {created_users}'))
        self.stdout.write(self.style.WARNING(f'  Пользователей обновлено: {updated_users}'))
        self.stdout.write(self.style.SUCCESS(f'  Обновлено без изменений: {updated_tab_only}'))
        if skipped_rows:
            self.stdout.write(self.style.ERROR(f'  Пропущено строк:       {skipped_rows}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
