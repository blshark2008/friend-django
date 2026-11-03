import csv
import re
from django.core.management.base import BaseCommand, CommandError
from accounts.models import User, Department, Position


def parse_name(full_name):
    """Разбирает 'Фамилия Имя Отчество' на части."""
    parts = full_name.strip().split()
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        return parts[0], parts[1], ''
    elif len(parts) == 1:
        return parts[0], '', ''
    return '', '', ''


def normalize_name(name):
    """Нормализует имя для поиска: убирает лишние пробелы, приводит к нижнему регистру."""
    return re.sub(r'\s+', ' ', name.strip().lower())


class Command(BaseCommand):
    help = 'Импорт списка сотрудников из CSV-файла'

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

        # Проверяем заголовок
        header = [c.strip() for c in rows[0]]
        self.stdout.write(f'Заголовок: {header}')

        current_department = None
        created_departments = 0
        created_positions = 0
        updated_users = 0
        created_users = 0
        skipped_rows = 0

        # Пропускаем заголовок
        for row in rows[1:]:
            # Убираем пустые строки и пробелы
            row = [c.strip() for c in row]
            if not any(row):
                continue

            # Определяем: это подразделение или сотрудник?
            # Подразделение: первая ячейка не начинается с цифры (или это заголовок типа "Аппарат управления")
            # Сотрудник: первая ячейка — цифра (номер)
            first_cell = row[0] if row else ''

            # Проверяем, начинается ли первая ячейка с цифры (номер сотрудника)
            if first_cell and re.match(r'^\d', first_cell):
                # Это строка сотрудника
                # Формат: №,Сотрудник,Должность,Вид занятости
                if len(row) < 3:
                    self.stdout.write(f'  Пропуск (мало колонок): {row}')
                    skipped_rows += 1
                    continue

                employee_num = row[0]  # номер
                full_name = row[1]     # ФИО
                position_name = row[2] if len(row) > 2 else ''  # должность

                if not full_name:
                    self.stdout.write(f'  Пропуск (нет ФИО, строка {employee_num})')
                    skipped_rows += 1
                    continue

                # Разбираем ФИО
                last_name, first_name, patronymic = parse_name(full_name)

                if not last_name:
                    self.stdout.write(f'  Пропуск (нет фамилии, строка {employee_num})')
                    skipped_rows += 1
                    continue

                # Создаём/находим подразделение
                if not current_department:
                    self.stdout.write(f'  Внимание: сотрудник {full_name} без подразделения')
                    skipped_rows += 1
                    continue

                # Создаём/находим должность
                position, pos_created = Position.objects.get_or_create(
                    name=position_name,
                    defaults={'department': current_department},
                )
                if pos_created:
                    created_positions += 1
                elif position.department_id != current_department.pk:
                    position.department = current_department
                    position.save(update_fields=['department'])

                # Ищем пользователя по username (фамилия латиницей + кириллицей)
                user = None

                # По email (фамилия@...)
                email_guess = f'{last_name.lower()}@company.local'
                try:
                    user = User.objects.get(email=email_guess)
                except User.DoesNotExist:
                    pass

                # По username (фамилия)
                if not user:
                    username_guess = last_name.lower()
                    try:
                        user = User.objects.get(username=username_guess)
                    except User.DoesNotExist:
                        pass

                # По ФИО (перебор всех пользователей — медленно, но надёжно для небольшого списка)
                if not user:
                    norm_last = normalize_name(last_name)
                    norm_first = normalize_name(first_name)
                    norm_patronymic = normalize_name(patronymic)

                    for u in User.objects.all():
                        u_parts = normalize_name(u.last_name), normalize_name(u.first_name), normalize_name(u.patronymic)
                        if (norm_last == u_parts[0] and norm_first == u_parts[1]):
                            user = u
                            break

                if user:
                    # Обновляем существующего пользователя
                    user.last_name = last_name
                    user.first_name = first_name
                    if patronymic:
                        user.patronymic = patronymic
                    user.department = current_department
                    user.position = position
                    user.save(update_fields=['last_name', 'first_name', 'patronymic', 'department', 'position'])
                    updated_users += 1
                    self.stdout.write(
                        f'  Обновлён: {full_name} → {current_department.name} / {position_name}',
                        self.style.WARNING
                    )
                else:
                    # Создаём нового пользователя
                    username = last_name.lower()
                    # Проверяем уникальность username
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
                        department=current_department,
                        position=position,
                        password='temp12345',  # временный пароль
                    )
                    created_users += 1
                    self.stdout.write(
                        f'  Создан: {full_name} → {current_department.name} / {position_name}',
                        self.style.SUCCESS
                    )

            else:
                # Это подразделение
                dept_name = first_cell
                if dept_name:
                    current_department, dept_created = Department.objects.get_or_create(
                        name=dept_name,
                    )
                    if dept_created:
                        created_departments += 1
                        self.stdout.write(
                            f'  Создано подразделение: {dept_name}',
                            self.style.SUCCESS
                        )
                    else:
                        self.stdout.write(f'  Подразделение существует: {dept_name}')

        # Итоги
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('ИТОГИ ИМПОРТА:'))
        self.stdout.write(self.style.SUCCESS(f'  Подразделений создано:  {created_departments}'))
        self.stdout.write(self.style.SUCCESS(f'  Должностей создано:    {created_positions}'))
        self.stdout.write(self.style.SUCCESS(f'  Пользователей создано: {created_users}'))
        self.stdout.write(self.style.WARNING(f'  Пользователей обновлено: {updated_users}'))
        if skipped_rows:
            self.stdout.write(self.style.ERROR(f'  Пропущено строк:       {skipped_rows}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
