from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class Department(models.Model):
    """Справочник подразделений."""
    name = models.CharField('Наименование', max_length=255)
    code_1c = models.CharField('Код в 1С', max_length=50, blank=True, unique=True, null=True)
    parent = models.ForeignKey(
        'self', verbose_name='Вышестоящее подразделение',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='children',
    )
    is_active = models.BooleanField('Активно', default=True)

    class Meta:
        verbose_name = 'Подразделение'
        verbose_name_plural = 'Подразделения'

    def __str__(self):
        return self.name


class Position(models.Model):
    """Справочник должностей."""
    name = models.CharField('Наименование', max_length=255)
    code_1c = models.CharField('Код в 1С', max_length=50, blank=True, unique=True, null=True)
    department = models.ForeignKey(
        Department, verbose_name='Подразделение',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='positions',
    )
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Должность'
        verbose_name_plural = 'Должности'

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Пользователь корпоративного приложения."""
    last_name = models.CharField('Фамилия', max_length=150)  # есть в AbstractUser, но переопределяем verbose
    first_name = models.CharField('Имя', max_length=150)     # тоже есть
    patronymic = models.CharField('Отчество', max_length=150, blank=True)
    groups = models.ManyToManyField(
        'auth.Group', verbose_name='группы',
        blank=True, related_name='custom_user_set',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission', verbose_name='права доступа',
        blank=True, related_name='custom_user_set',
        related_query_name='custom_user',
    )
    corporate_phone = models.CharField(
        'Корпоративный телефон', max_length=20, blank=True,
        validators=[RegexValidator(r'^\+?\d{10,15}$', 'Формат: +7XXXXXXXXXX')],
    )
    personal_phone = models.CharField(
        'Личный телефон', max_length=20, blank=True,
        validators=[RegexValidator(r'^\+?\d{10,15}$', 'Формат: +7XXXXXXXXXX')],
    )
    snils = models.CharField(
        'СНИЛС', max_length=14, blank=True, unique=True, null=True,
        validators=[RegexValidator(r'^\d{3}-\d{3}-\d{3} \d{2}$', 'Формат: 000-000-000 00')],
    )
    corporate_email = models.EmailField('Корпоративный Email', blank=True)  # есть в AbstractUser
    personal_email = models.EmailField('Личный Email', blank=True)
    department = models.ForeignKey(
        Department, verbose_name='Подразделение',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='employees',
    )
    position = models.ForeignKey(
        Position, verbose_name='Должность',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='employees',
    )
    employee_code_1c = models.CharField('Код сотрудника в 1С', max_length=50, blank=True, null=True, unique=True)
    tab_number = models.CharField('Табельный номер', max_length=50, blank=True, unique=True, null=True)
    domain_account = models.CharField('Доменная учётная запись', max_length=100, blank=True, null=True)
    hire_date = models.DateField('Дата приёма', blank=True, null=True)
    fire_date = models.DateField('Дата увольнения', blank=True, null=True)
    is_fired = models.BooleanField('Уволен', default=False)

    # Статусы для процесса архивирования
    STATUS_ACTIVE = 'active'
    STATUS_MARKED = 'marked'
    STATUS_ARCHIVED = 'archived'

    ARCHIVE_STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Активный'),
        (STATUS_MARKED, 'Помечен к архивированию'),
        (STATUS_ARCHIVED, 'В архиве'),
    ]

    archive_status = models.CharField(
        'Статус архивирования',
        max_length=20,
        choices=ARCHIVE_STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    marked_archive_date = models.DateField('Дата пометки в архив', blank=True, null=True)
    archive_date = models.DateField('Дата перемещения в архив', blank=True, null=True)
    is_admin = models.BooleanField('Администратор', default=False, help_text='Автоматически не архивируется при импорте')
    is_mol = models.BooleanField('МОЛ', default=False, help_text='Материально-ответственное лицо подразделения')

    # ===== Настройки каналов связи для сообщений =====
    max_id = models.CharField('ID в MAX', max_length=100, blank=True, default='', help_text='ID пользователя в системе MAX')
    max_chat_id = models.BigIntegerField('Chat ID в MAX', null=True, blank=True,
                                         help_text='ID чата/диалога для отправки ответов через MAX')
    telegram_id = models.CharField('ID в Telegram', max_length=100, blank=True, default='', help_text='ID пользователя в Telegram')
    notify_max = models.BooleanField('Уведомления через MAX', default=False, help_text='Разрешить отправку сообщений через MAX')
    notify_telegram = models.BooleanField('Уведомления через Telegram', default=False, help_text='Разрешить отправку сообщений через Telegram')
    notify_corporate_email = models.BooleanField('Уведомления на корп. почту', default=False, help_text='Разрешить отправку на корпоративный email')
    notify_personal_email = models.BooleanField('Уведомления на лич. почту', default=False, help_text='Разрешить отправку на личный email')

    # ===== Интеграция с Skillspace =====
    uuid_skillspace = models.CharField(
        'UUID студента на Skillspace', max_length=100, blank=True, default='',
        help_text='UUID студента на платформе Skillspace',
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
