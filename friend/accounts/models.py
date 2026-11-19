from django.contrib.auth.models import AbstractUser, Group as AuthGroup
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


class InternalGroup(models.Model):
    """Внутренняя группа прав доступа приложения."""
    name = models.CharField('Название', max_length=150, unique=True)
    description = models.TextField('Описание', blank=True)
    code = models.CharField('Код группы', max_length=50, unique=True, help_text='Уникальный технический код группы')
    is_active = models.BooleanField('Активна', default=True)
    is_system = models.BooleanField('Системная', default=False, help_text='Системные группы не удаляются')
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Внутренняя группа'
        verbose_name_plural = 'Внутренние группы'
        ordering = ['name']

    def __str__(self):
        return self.name


class ADSyncSettings(models.Model):
    """Настройки синхронизации с Active Directory."""
    ad_server = models.CharField('Сервер AD', max_length=255, help_text='IP или hostname контроллера домена')
    ad_port = models.IntegerField('Порт LDAP', default=389)
    ad_use_ssl = models.BooleanField('Использовать SSL', default=False)
    ad_base_dn = models.CharField('Base DN', max_length=500, help_text='Например: DC=domain,DC=local')
    ad_bind_dn = models.CharField('DN для привязки', max_length=500, help_text='Учётная запись для поиска в AD')
    ad_bind_password = models.CharField('Пароль для привязки', max_length=500, blank=True, help_text='Хранится в открытом виде')
    ad_user_search_base = models.CharField('Поиск пользователей', max_length=500, blank=True,
                                            help_text='Опционально: поддерево для поиска пользователей')
    ad_group_search_base = models.CharField('Поиск групп', max_length=500, blank=True,
                                             help_text='Опционально: поддерево для поиска групп')
    ad_user_object_class = models.CharField('ObjectClass пользователя', max_length=50, default='person')
    ad_user_samaccountname_field = models.CharField('Поле samAccountName', max_length=50, default='sAMAccountName')
    ad_user_memberof_field = models.CharField('Поле членства в группах', max_length=50, default='memberOf')
    ad_group_object_class = models.CharField('ObjectClass группы', max_length=50, default='group')
    ad_group_cn_field = models.CharField('Поле CN группы', max_length=50, default='cn')
    ad_group_samaccountname_field = models.CharField('Поле samAccountName группы', max_length=50, default='sAMAccountName')
    sync_on_login = models.BooleanField('Синхронизация при входе', default=False,
                                         help_text='Автоматически синхронизировать группы при каждом входе пользователя')
    sync_interval_hours = models.PositiveIntegerField('Интервал синхронизации (часы)', default=24,
                                                       help_text='Периодичность фоновой синхронизации')
    last_sync = models.DateTimeField('Последняя синхронизация', null=True, blank=True)
    is_enabled = models.BooleanField('Синхронизация включена', default=False)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Настройка AD синхронизации'
        verbose_name_plural = 'Настройки AD синхронизации'

    def __str__(self):
        status = 'Вкл' if self.is_enabled else 'Выкл'
        return f'AD Sync [{status}] {self.ad_server}'

    @classmethod
    def get_settings(cls):
        """Получить единственную настройку или создать по умолчанию."""
        return cls.objects.first()

    @classmethod
    def get_enabled(cls):
        """Проверить, включена ли синхронизация."""
        settings = cls.objects.first()
        return settings is not None and settings.is_enabled


class GroupMapping(models.Model):
    """Связка AD-группы с внутренней группой прав."""
    ad_group_name = models.CharField('Имя AD-группы (CN)', max_length=255,
                                      help_text='Например: FG_APP_READ или полное DN')
    ad_group_dn = models.CharField('DN AD-группы', max_length=500, blank=True,
                                    help_text='Полное Distinguished Name группы в AD')
    ad_group_description = models.TextField('Описание AD-группы', blank=True, editable=False)
    internal_group = models.ForeignKey(
        InternalGroup, verbose_name='Внутренняя группа',
        on_delete=models.CASCADE, related_name='ad_mappings',
    )
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Связка AD-группы'
        verbose_name_plural = 'Связки AD-групп'
        ordering = ['ad_group_name']
        unique_together = ['ad_group_name', 'internal_group']
        indexes = [
            models.Index(fields=['ad_group_name']),
            models.Index(fields=['internal_group']),
        ]

    def __str__(self):
        return f'{self.ad_group_name} -> {self.internal_group}'


class MenuSection(models.Model):
    """Раздел меню приложения."""
    name = models.CharField('Название раздела', max_length=255)
    code = models.CharField('Код раздела', max_length=100, unique=True,
                            help_text='Уникальный технический код (например: "users", "training")')
    icon = models.CharField('Иконка (Bootstrap Icons)', max_length=100, default='bi-circle',
                            help_text='Например: bi-people, bi-mortarboard, bi-building')
    description = models.TextField('Описание', blank=True)
    order = models.PositiveIntegerField('Порядок', default=0,
                                        help_text='Меньшее значение = выше в меню')
    is_active = models.BooleanField('Активен', default=True,
                                    help_text='Неактивные разделы не отображаются в меню')
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Раздел меню'
        verbose_name_plural = 'Разделы меню'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def get_menu_items(self):
        """Получить все активные пункты меню этого раздела."""
        return self.menu_items.filter(is_active=True).order_by('order', 'name')


class MenuItem(models.Model):
    """Пункт меню."""
    section = models.ForeignKey(
        MenuSection, verbose_name='Раздел',
        on_delete=models.CASCADE, related_name='menu_items',
    )
    name = models.CharField('Название', max_length=255)
    url_name = models.CharField('Имя URL-шаблона', max_length=255,
                                help_text='Например: accounts:user_list, training:type_list')
    url_pattern = models.CharField('Шаблон URL', max_length=500, blank=True,
                                   help_text='Полный URL или имя шаблона')
    icon = models.CharField('Иконка', max_length=100, blank=True,
                            help_text='Например: bi-list-ul, bi-person')
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Пункт меню'
        verbose_name_plural = 'Пункты меню'
        ordering = ['section__order', 'order', 'name']
        unique_together = ['section', 'url_name']

    def __str__(self):
        return f'{self.section.name} — {self.name}'

    def get_absolute_url(self):
        """Получить URL по имени шаблона."""
        if self.url_pattern:
            return self.url_pattern
        try:
            from django.urls import reverse
            return reverse(self.url_name)
        except Exception:
            return '#'


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
    internal_groups = models.ManyToManyField(
        'InternalGroup', verbose_name='Внутренние группы',
        blank=True, related_name='users',
        help_text='Группы прав, назначенные пользователю',
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

    def get_full_name(self):
        """Возвращает полное ФИО с отчеством."""
        parts = [self.last_name, self.first_name]
        if self.patronymic:
            parts.append(self.patronymic)
        return ' '.join(parts)

    def get_ad_groups(self):
        """Получить список AD-групп пользователя из маппингов."""
        mappings = GroupMapping.objects.filter(is_active=True)
        return mappings.values_list('ad_group_name', flat=True)

    def refresh_groups_from_ad(self):
        """Синхронизировать внутренние группы на основе AD-групп."""
        from .services import ADGroupSyncService
        return ADGroupSyncService.sync_user_groups(self)
