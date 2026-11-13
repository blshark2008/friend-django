from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class Resource(models.Model):
    """Общая сущность: любой объект, доступ к которому учитываем."""
    class Type(models.TextChoices):
        NETWORK = "network", "Сетевой ресурс"
        SOFTWARE = "software", "Программа"
        REMOTE = "remote", "Удалённый доступ"
        SERVER = "server", "Сервер"
        DATABASE = "database", "База данных"
        APPLICATION = "application", "Приложение / Веб-сервис"
        STORAGE = "storage", "Хранилище"
        CLOUD = "cloud", "Облачный ресурс"
        HARDWARE = "hardware", "Оборудование"

    name = models.CharField('Наименование', max_length=255)
    type = models.CharField(
        'Тип ресурса', max_length=20, choices=Type.choices,
        db_index=True,
    )
    description = models.TextField('Описание', blank=True)
    owner = models.ForeignKey(
        'accounts.Department', verbose_name='Ответственное подразделение',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='resources',
    )
    is_active = models.BooleanField('Активен', default=True)

    last_audit_date = models.DateField(
        'Дата последней актуализации', null=True, blank=True,
    )

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Ресурс'
        verbose_name_plural = 'Ресурсы'
        ordering = ['name']
        indexes = [
            models.Index(fields=['type', 'is_active']),
        ]

    def __str__(self):
        return f'{self.get_type_display()}: {self.name}'

    @property
    def is_audit_valid(self):
        """Проверяет, что актуализация не старше 6 месяцев."""
        if not self.last_audit_date:
            return False
        six_months_ago = timezone.now().date()
        from datetime import timedelta
        six_months_ago = six_months_ago - timedelta(days=183)
        return self.last_audit_date >= six_months_ago

    @property
    def detail(self):
        """Возвращает детальную запись по типу ресурса."""
        try:
            return self.network_detail
        except NetworkResourceDetail.DoesNotExist:
            pass
        try:
            return self.software_detail
        except SoftwareResourceDetail.DoesNotExist:
            pass
        try:
            return self.remote_access_detail
        except RemoteAccessDetail.DoesNotExist:
            pass
        try:
            return self.server_detail
        except ServerResourceDetail.DoesNotExist:
            pass
        try:
            return self.database_detail
        except DatabaseResourceDetail.DoesNotExist:
            pass
        try:
            return self.application_detail
        except ApplicationResourceDetail.DoesNotExist:
            pass
        try:
            return self.storage_detail
        except StorageResourceDetail.DoesNotExist:
            pass
        try:
            return self.cloud_detail
        except CloudResourceDetail.DoesNotExist:
            pass
        try:
            return self.hardware_detail
        except HardwareResourceDetail.DoesNotExist:
            pass
        return None

    @property
    def grants_count(self):
        return self.grants.filter(is_active=True).count()

    @property
    def active_users_count(self):
        return self.grants.filter(is_active=True).values_list('user_id', flat=True).distinct().count()


class NetworkResourceDetail(models.Model):
    """Детали сетевого ресурса."""
    resource = models.OneToOneField(
        Resource, on_delete=models.CASCADE, primary_key=True,
        related_name='network_detail',
    )
    host = models.GenericIPAddressField('IP-адрес / hostname')
    port = models.PositiveIntegerField('Порт', null=True, blank=True)
    protocol = models.CharField('Протокол', max_length=50, blank=True, default='')
    share_path = models.CharField('Путь к шаре', max_length=500, blank=True, default='')

    def __str__(self):
        return f'Network: {self.resource.name} ({self.host}{":" + str(self.port) if self.port else ""})'


class SoftwareResourceDetail(models.Model):
    """Детали программного ресурса."""
    resource = models.OneToOneField(
        Resource, on_delete=models.CASCADE, primary_key=True,
        related_name='software_detail',
    )
    vendor = models.CharField('Разработчик / вендор', max_length=255, blank=True)
    version = models.CharField('Версия', max_length=50, blank=True, default='')
    license_count = models.PositiveIntegerField('Кол-во лицензий', null=True, blank=True)
    license_key = models.CharField('Ключ лицензии', max_length=255, blank=True, default='')

    def __str__(self):
        return f'Software: {self.resource.name} v{self.version or "?"}'


class RemoteAccessDetail(models.Model):
    """Детали удалённого доступа."""
    resource = models.OneToOneField(
        Resource, on_delete=models.CASCADE, primary_key=True,
        related_name='remote_access_detail',
    )
    gateway = models.CharField('Шлюз / адрес', max_length=255)
    protocol = models.CharField('Протокол', max_length=50)  # VPN, RDP, SSH...
    port = models.PositiveIntegerField('Порт', null=True, blank=True)

    def __str__(self):
        return f'Remote: {self.resource.name} ({self.protocol}://{self.gateway})'


class ServerResourceDetail(models.Model):
    """Детали сервера / ОС."""
    resource = models.OneToOneField(
        Resource, on_delete=models.CASCADE, primary_key=True,
        related_name='server_detail',
    )
    hostname = models.CharField('Hostname', max_length=255)
    os_type = models.CharField('ОС', max_length=50, blank=True, default='')
    ssh_port = models.PositiveIntegerField('SSH-порт', default=22)
    ip_address = models.GenericIPAddressField('IP-адрес', null=True, blank=True)

    def __str__(self):
        return f'Server: {self.resource.name} ({self.hostname})'


class DatabaseResourceDetail(models.Model):
    """Детали базы данных."""
    resource = models.OneToOneField(
        Resource, on_delete=models.CASCADE, primary_key=True,
        related_name='database_detail',
    )
    host = models.GenericIPAddressField('Хост')
    port = models.PositiveIntegerField('Порт', default=5432)
    database_name = models.CharField('Имя БД', max_length=100)
    engine = models.CharField('Движок', max_length=50, blank=True, default='postgresql')

    def __str__(self):
        return f'DB: {self.resource.name} ({self.database_name}@{self.host})'


class ApplicationResourceDetail(models.Model):
    """Детали приложения / веб-сервиса."""
    resource = models.OneToOneField(
        Resource, on_delete=models.CASCADE, primary_key=True,
        related_name='application_detail',
    )
    url = models.URLField('URL-адрес', blank=True)
    environment = models.CharField('Среда', max_length=50, blank=True, default='')  # prod, staging, dev
    api_endpoint = models.CharField('API endpoint', max_length=500, blank=True, default='')

    def __str__(self):
        return f'App: {self.resource.name}'


class StorageResourceDetail(models.Model):
    """Детали хранилища."""
    resource = models.OneToOneField(
        Resource, on_delete=models.CASCADE, primary_key=True,
        related_name='storage_detail',
    )
    capacity_gb = models.PositiveIntegerField('Ёмкость (ГБ)', null=True, blank=True)
    used_gb = models.PositiveIntegerField('Использовано (ГБ)', null=True, blank=True)
    mount_point = models.CharField('Точка монтирования', max_length=500, blank=True, default='')
    filesystem = models.CharField('Файловая система', max_length=50, blank=True, default='')

    def __str__(self):
        return f'Storage: {self.resource.name}'


class CloudResourceDetail(models.Model):
    """Детали облачного ресурса."""
    resource = models.OneToOneField(
        Resource, on_delete=models.CASCADE, primary_key=True,
        related_name='cloud_detail',
    )
    provider = models.CharField('Провайдер', max_length=100)  # AWS, GCP, Yandex Cloud...
    region = models.CharField('Регион', max_length=100, blank=True, default='')
    account_id = models.CharField('ID аккаунта / проекта', max_length=100, blank=True, default='')

    def __str__(self):
        return f'Cloud: {self.resource.name} ({self.provider})'


class HardwareResourceDetail(models.Model):
    """Детали оборудования."""
    resource = models.OneToOneField(
        Resource, on_delete=models.CASCADE, primary_key=True,
        related_name='hardware_detail',
    )
    serial_number = models.CharField('Серийный номер', max_length=100, blank=True)
    model = models.CharField('Модель', max_length=255, blank=True)
    location = models.CharField('Расположение', max_length=255, blank=True)

    def __str__(self):
        return f'Hardware: {self.resource.name}'


class AccessGroup(models.Model):
    """Группа доступа к ресурсам.

    Наименование конструируется по принципу:
    <ТИП>-<РЕСУРС>-<ОБЛАСТЬ>-<УРОВЕНЬ>
    """

    # Mapping: префикс типа -> категория, допустимые уровни
    TYPE_PREFIXES = {
        # Файловые хранилища
        'fs': {'category': 'Файловые хранилища', 'levels': ['ro', 'rw', 'adm']},
        # Приложения и веб-сервисы
        'app': {'category': 'Приложения и веб-сервисы', 'levels': ['view', 'edit', 'admin', 'user', 'approver']},
        # Базы данных
        'db': {'category': 'Базы данных', 'levels': ['ro', 'rw', 'ddl', 'admin']},
        # Серверы и ОС
        'srv': {'category': 'Серверы и ОС', 'levels': ['user', 'ops', 'sudo', 'root']},
        # Контейнеры и оркестрация
        'ctr': {'category': 'Контейнеры и оркестрация', 'levels': ['ops', 'build', 'admin']},
        # Сетевой доступ
        'net': {'category': 'Сетевой доступ', 'levels': ['user', 'admin', 'guest']},
        # Физический доступ (СКУД)
        'hvac': {'category': 'Физический доступ', 'levels': ['access', 'admin']},
        # Административные привилегии
        'adm': {'category': 'Административные привилегии', 'levels': ['admin', 'auditor']},
        # Мониторинг и ИБ
        'mon': {'category': 'Мониторинг и ИБ', 'levels': ['view', 'ops', 'admin']},
        # Резервное копирование
        'bck': {'category': 'Резервное копирование', 'levels': ['ops', 'restore', 'admin']},
        # Специализированные научные ресурсы
        'sci': {'category': 'Специализированные научные ресурсы', 'levels': ['user', 'queue', 'admin']},
        # Медицинские системы
        'med': {'category': 'Медицинские системы', 'levels': ['user', 'operator', 'view', 'admin']},
        # Закупки и финансы
        'prc': {'category': 'Закупки и финансы', 'levels': ['user', 'approver', 'admin']},
        # Кадровые и орг. системы
        'hr': {'category': 'Кадровые и орг. системы', 'levels': ['user', 'hr', 'admin']},
        # Проектные данные
        'prj': {'category': 'Проектные данные', 'levels': ['ro', 'rw', 'lead']},
        # Обучающие системы
        'edu': {'category': 'Обучающие системы', 'levels': ['student', 'teacher', 'admin']},
    }

    name = models.CharField('Наименование', max_length=255)
    old_name = models.CharField(
        'Старое наименование', max_length=255, blank=True, default='',
        help_text='Прежнее наименование группы (до перехода на новый формат)',
    )
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активна', default=True)

    # Компоненты наименования: <ТИП>-<РЕСУРС>-<ОБЛАСТЬ>-<УРОВЕНЬ>
    type_prefix = models.CharField(
        'Тип ресурса (префикс)', max_length=10, blank=True, default='',
        choices=[(k, f'{k} — {v["category"]}') for k, v in TYPE_PREFIXES.items()],
        help_text='Префикс типа ресурса (например: fs, app, db, srv)',
    )
    resource_name = models.CharField(
        'Ресурс', max_length=100, blank=True, default='',
        help_text='Идентификатор или наименование ресурса',
    )
    area = models.CharField(
        'Область', max_length=100, blank=True, default='',
        help_text='Область / подразделение / среда',
    )
    access_level = models.CharField(
        'Уровень доступа', max_length=20, blank=True, default='',
        help_text='Допустимые уровни зависят от типа ресурса',
    )

    # Аудит группы
    audited = models.BooleanField(
        'Проведён аудит', default=False,
        help_text='Отметить, что группа прошла проверку',
    )
    audited_at = models.DateTimeField(
        'Дата аудита', null=True, blank=True,
        help_text='Дата проведения аудита группы',
    )

    # Привязка к ресурсу
    resource = models.ForeignKey(
        'Resource', verbose_name='Ресурс',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='access_groups',
        help_text='Ресурс, к которому привязана группа доступа',
    )

    # Закреплённое подразделение
    pinned_department = models.ForeignKey(
        'accounts.Department', verbose_name='Закреплённое подразделение',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pinned_access_groups',
    )

    # Поля для будущей синхронизации с AD
    ad_group_dn = models.CharField(
        'DN группы AD', max_length=500, blank=True, default='',
        help_text='Distinguished Name группы в Active Directory',
    )
    ad_sync_enabled = models.BooleanField(
        'Синхронизация с AD', default=False,
        help_text='Включить синхронизацию группы с AD',
    )
    ad_sync_last_date = models.DateTimeField(
        'Последняя синхронизация с AD', null=True, blank=True,
    )

    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Группа доступа'
        verbose_name_plural = 'Группы доступа'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['name'], name='unique_access_group_name'),
        ]

    def __str__(self):
        return self.name

    @property
    def grants_count(self):
        return self.grants.filter(is_active=True).count()

    def generate_name(self):
        """Конструирует наименование по правилу: ТИП-РЕСУРС-ОБЛАСТЬ-УРОВЕНЬ."""
        parts = []
        if self.type_prefix:
            parts.append(self.type_prefix)
        if self.resource_name:
            parts.append(self.resource_name)
        if self.area:
            parts.append(self.area)
        if self.access_level:
            parts.append(self.access_level)
        return '-'.join(parts)

    def parse_name(self):
        """Распаковывает наименование на компоненты."""
        if not self.name:
            return {}
        parts = self.name.split('-')
        result = {}
        result['type_prefix'] = parts[0] if len(parts) > 0 else ''
        result['resource_name'] = parts[1] if len(parts) > 1 else ''
        result['area'] = parts[2] if len(parts) > 2 else ''
        result['access_level'] = parts[3] if len(parts) > 3 else ''
        # Если частей больше 4 — остаток добавляем к access_level
        if len(parts) > 4:
            result['access_level'] = '-'.join(parts[3:])
        return result

    def get_type_category(self):
        """Возвращает категорию по префиксу типа."""
        info = self.TYPE_PREFIXES.get(self.type_prefix, {})
        return info.get('category', '')

    def get_valid_levels(self):
        """Возвращает допустимые уровни для текущего префикса типа."""
        info = self.TYPE_PREFIXES.get(self.type_prefix, {})
        return info.get('levels', [])

    @property
    def display_name(self):
        """Возвращает наименование для отображения.

        Если новое имя (из компонентов) заполнено — показывает
        «новое_имя (старое_имя)». Если нет — старое имя.
        """
        generated = self.generate_name()
        if generated:
            if self.old_name:
                return f'{generated} ({self.old_name})'
            return generated
        if self.old_name:
            return self.old_name
        return self.name or '—'


class AccessGrant(models.Model):
    """Универсальный грант доступа: пользователь/группа → ресурс."""

    grant_type = models.CharField(
        'Тип гранта', max_length=10, choices=[
            ('user', 'Пользователь'),
            ('group', 'Группа'),
        ], default='user',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name='access_grants',
    )
    group = models.ForeignKey(
        AccessGroup, on_delete=models.CASCADE, null=True, blank=True,
        related_name='grants',
    )
    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name='grants',
    )
    is_active = models.BooleanField('Активен', default=True)
    granted_at = models.DateTimeField('Выдан', auto_now_add=True)
    expires_at = models.DateField('Истекает', null=True, blank=True)
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='grants_issued',
    )
    revoked_at = models.DateTimeField('Отозван', null=True, blank=True)
    justification = models.TextField('Обоснование', blank=True)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Грант доступа'
        verbose_name_plural = 'Гранты доступа'
        unique_together = ['user', 'group', 'resource']
        ordering = ['resource__name']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(grant_type='user', user__isnull=False, group__isnull=True)
                    | models.Q(grant_type='group', user__isnull=True, group__isnull=False)
                ),
                name='grant_type_consistency',
            ),
        ]

    def __str__(self):
        who = self.user.get_full_name() if self.user else (self.group.name if self.group else '?')
        return f'{who} → {self.resource.name}'

    @property
    def is_expired(self):
        if self.expires_at:
            return self.expires_at < timezone.now().date()
        return False

    @property
    def is_revoked(self):
        return self.revoked_at is not None or not self.is_active


class AccessRequest(models.Model):
    """Заявка на предоставление доступа."""
    class Status(models.TextChoices):
        NEW = "new", "Новая"
        APPROVED = "approved", "Согласована"
        REJECTED = "rejected", "Отклонена"
        GRANTED = "granted", "Доступ выдан"
        DONE = "done", "Закрыта"

    requester = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='access_requests',
    )
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    level = models.CharField('Уровень доступа', max_length=10)
    justification = models.TextField('Обоснование', blank=True)
    status = models.CharField(
        'Статус', max_length=10, choices=Status.choices, default=Status.NEW,
    )
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)
    approver = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approved_requests',
    )
    grant = models.OneToOneField(
        AccessGrant, null=True, blank=True, on_delete=models.SET_NULL,
    )
    rejection_reason = models.TextField('Причина отклонения', blank=True)

    class Meta:
        verbose_name = 'Заявка на доступ'
        verbose_name_plural = 'Заявки на доступ'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.requester.get_full_name()} → {self.resource.name} ({self.get_status_display()})'

    def approve(self, approver):
        self.status = self.Status.APPROVED
        self.approver = approver
        self.save()

    def grant_access(self, granted_by):
        """Создать AccessGrant и закрыть заявку."""
        grant = AccessGrant.objects.create(
            grant_type='user',
            user=self.requester,
            resource=self.resource,
            level=self.level,
            granted_by=granted_by,
            justification=self.justification,
        )
        self.grant = grant
        self.status = self.Status.GRANTED
        self.save()

    def reject(self, reason=''):
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.save()


class Role(models.Model):
    """Роль — набор групп доступа.

    Роль объединяет несколько групп доступа для назначения пользователям.
    Удаление переводит роль в архив (soft delete).
    """
    name = models.CharField('Наименование', max_length=255)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def groups_count(self):
        return self.groups.count()

    @property
    def active_groups_count(self):
        return self.groups.select_related('access_group').filter(
            access_group__is_active=True
        ).count()

    @property
    def group_containers_count(self):
        return self.group_containers.count()


class RoleGroup(models.Model):
    """Связь роли с группами доступа."""
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name='groups',
    )
    access_group = models.ForeignKey(
        AccessGroup, on_delete=models.CASCADE, related_name='role_groups',
    )
    added_at = models.DateTimeField('Добавлена', auto_now_add=True)
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='role_groups_added',
    )

    class Meta:
        verbose_name = 'Группа в роли'
        verbose_name_plural = 'Группы в ролях'
        unique_together = ['role', 'access_group']
        ordering = ['access_group__name']

    def __str__(self):
        return f'{self.role.name} → {self.access_group.name}'


class GroupContainer(models.Model):
    """Контейнер групп доступа.

    Контейнер объединяет группы доступа по смыслу для удобства
    управления и назначения в роли.
    Удаление переводит контейнер в архив (soft delete).
    """
    name = models.CharField('Наименование', max_length=255)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    # Группы доступа, входящие в контейнер
    groups = models.ManyToManyField(
        AccessGroup, through='GroupContainerGroup', blank=True,
        related_name='group_containers',
    )

    class Meta:
        verbose_name = 'Контейнер групп доступа'
        verbose_name_plural = 'Контейнеры групп доступа'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def groups_count(self):
        return self.groups.count()

    @property
    def active_groups_count(self):
        return self.groups.filter(is_active=True).count()


class GroupContainerGroup(models.Model):
    """Связь контейнера групп с группами доступа."""
    group_container = models.ForeignKey(
        GroupContainer, on_delete=models.CASCADE, related_name='container_groups',
    )
    access_group = models.ForeignKey(
        AccessGroup, on_delete=models.CASCADE, related_name='group_container_groups',
    )
    added_at = models.DateTimeField('Добавлена', auto_now_add=True)
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='container_groups_added',
    )

    class Meta:
        verbose_name = 'Группа в контейнере'
        verbose_name_plural = 'Группы в контейнерах'
        unique_together = ['group_container', 'access_group']
        ordering = ['access_group__name']

    def __str__(self):
        return f'{self.group_container.name} → {self.access_group.name}'


class RoleGroupContainer(models.Model):
    """Связь роли с контейнерами групп доступа."""
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name='group_containers',
    )
    group_container = models.ForeignKey(
        GroupContainer, on_delete=models.CASCADE, related_name='role_group_containers',
    )
    added_at = models.DateTimeField('Добавлен', auto_now_add=True)
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='role_group_containers_added',
    )

    class Meta:
        verbose_name = 'Контейнер групп в роли'
        verbose_name_plural = 'Контейнеры групп в ролях'
        unique_together = ['role', 'group_container']
        ordering = ['group_container__name']

    def __str__(self):
        return f'{self.role.name} → {self.group_container.name}'
