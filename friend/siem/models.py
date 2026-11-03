from django.db import models
from django.utils import timezone


# ============================================================================
# Хосты (агенты)
# ============================================================================

class Host(models.Model):
    """Зарегистрированный хост с агентом SIEM."""

    hostname = models.CharField('Имя хоста', max_length=100, unique=True)
    serial_number = models.CharField('Серийный номер', max_length=100, blank=True)
    os_info = models.CharField('ОС', max_length=255, blank=True)
    os_name = models.CharField('Наименование ОС', max_length=255, blank=True)
    os_type = models.CharField('Тип ОС', max_length=50, blank=True)  # linux, windows
    os_install_date = models.DateField('Дата установки ОС', null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField('MAC-адрес', max_length=17, blank=True)
    agent_version = models.CharField('Версия агента', max_length=20, blank=True)
    last_seen = models.DateTimeField('Последний контакт', null=True, blank=True)
    is_active = models.BooleanField('Активен', default=True)
    antivirus_installed = models.BooleanField('Антивирус установлен', default=False)
    antivirus_name = models.CharField('Антивирус', max_length=100, blank=True)
    antivirus_version = models.CharField('Версия антивируса', max_length=50, blank=True)
    antivirus_last_update = models.DateTimeField('Последнее обновление антивируса', null=True, blank=True)
    screen_lock_timeout = models.PositiveIntegerField('Таймаут блокировки экрана (мин)', null=True, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Хост'
        verbose_name_plural = 'Хосты'
        ordering = ['hostname']

    def __str__(self):
        return self.hostname

    @property
    def is_offline(self):
        """Хост считается оффлайн, если не был на связи > 24 часа."""
        if not self.last_seen:
            return True
        return (timezone.now() - self.last_seen).total_seconds() > 86400

    @property
    def total_events(self):
        return self.events.count()

    @property
    def critical_events_count(self):
        return self.events.filter(severity='critical').count()


# ============================================================================
# Снимки инвентаризации
# ============================================================================

class InventorySnapshot(models.Model):
    """Снимок инвентаризации хоста (железо, ОС, пакеты, порты)."""

    host = models.ForeignKey(
        Host, on_delete=models.CASCADE, related_name='snapshots',
        verbose_name='Хост',
    )
    collected_at = models.DateTimeField('Собрано', auto_now_add=True)
    cpu_model = models.CharField('Процессор', max_length=255, blank=True)
    cpu_temperature = models.FloatField('Температура CPU (°C)', null=True, blank=True)
    ram_mb = models.PositiveIntegerField('ОЗУ (МБ)', null=True, blank=True)
    disk_info = models.JSONField('Диски', default=dict)
    packages_count = models.PositiveIntegerField('Кол-во пакетов', null=True, blank=True)
    pending_updates = models.JSONField('Ожидают обновления', default=list)
    open_ports = models.JSONField('Открытые порты', default=list)
    raw = models.JSONField('Полные данные', default=dict)

    class Meta:
        verbose_name = 'Снимок инвентаризации'
        verbose_name_plural = 'Снимки инвентаризации'
        ordering = ['-collected_at']

    def __str__(self):
        return f"{self.host.hostname} — {self.collected_at:%Y-%m-%d %H:%M}"


# ============================================================================
# История входов
# ============================================================================

class ScreenLockLog(models.Model):
    """Переходы состояния блокировки экрана (только смены состояния)."""

    STATE_CHOICES = [
        ('locked', 'Заблокирован'),
        ('unlocked', 'Разблокирован'),
    ]

    host = models.ForeignKey(
        Host, on_delete=models.CASCADE, related_name='screen_lock_logs',
        verbose_name='Хост',
    )
    state = models.CharField('Состояние', max_length=20, choices=STATE_CHOICES, db_index=True, default='unlocked')
    timestamp = models.DateTimeField('Время перехода', db_index=True)
    date = models.DateField('Дата', db_index=True, null=True, blank=True)
    username = models.CharField('Логин', max_length=100, blank=True)
    session_id = models.CharField('ID сессии', max_length=50, blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Переход блокировки'
        verbose_name_plural = 'Переходы блокировки'
        ordering = ['-timestamp']
        constraints = [
            models.UniqueConstraint(
                fields=['host', 'date', 'state'],
                name='uq_screenlocklog_host_date_state',
            ),
        ]
        indexes = [
            models.Index(fields=['host', 'timestamp']),
            models.Index(fields=['state', 'timestamp']),
        ]

    def __str__(self):
        state = 'заблокирован' if self.is_locked else 'разблокирован'
        return f"{self.host.hostname} — {state} ({self.timestamp:%Y-%m-%d %H:%M})"


class RecentLogin(models.Model):
    """Последние входы пользователей на хосты."""

    host = models.ForeignKey(
        Host, on_delete=models.CASCADE, related_name='recent_logins',
        verbose_name='Хост',
    )
    username = models.CharField('Логин', max_length=100, db_index=True)
    source = models.CharField('Источник входа', max_length=100, blank=True)  # console, ssh, rdp, IP
    login_time = models.DateTimeField('Время входа', db_index=True)
    matched_user = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='matched_logins',
        verbose_name='Сотрудник из Accounts',
    )
    is_matched = models.BooleanField('Сопоставлен с сотрудником', default=False)
    is_screen_locked = models.BooleanField('Экран заблокирован', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Последний вход'
        verbose_name_plural = 'Последние входы'
        ordering = ['-login_time']
        constraints = [
            models.UniqueConstraint(
                fields=['host', 'username', 'login_time'],
                name='uq_recent_login_host_user_time',
            ),
        ]
        indexes = [
            models.Index(fields=['username', 'login_time']),
            models.Index(fields=['host', 'login_time']),
            models.Index(fields=['matched_user', 'login_time']),
        ]

    def __str__(self):
        matched = f" ({self.matched_user})" if self.matched_user else ""
        return f"{self.username} @ {self.host.hostname}{matched} — {self.login_time:%Y-%m-%d %H:%M}"


# ============================================================================
# События безопасности
# ============================================================================

class SecurityEvent(models.Model):
    """Событие безопасности с любого хоста."""

    class Severity(models.TextChoices):
        INFO = 'info', 'Информация'
        WARNING = 'warning', 'Предупреждение'
        ERROR = 'error', 'Ошибка'
        CRITICAL = 'critical', 'Критично'

    class EventType(models.TextChoices):
        AUTH_FAILED = 'auth_failed', 'Неудачный вход'
        AUTH_SUCCESS = 'auth_success', 'Успешный вход'
        SUDO_USED = 'sudo_used', 'Использован sudo'
        FILE_CHANGED = 'file_changed', 'Изменение файла'
        UID0_ADDED = 'uid0_added', 'UID 0 пользователь'
        SUID_ADDED = 'suid_added', 'Новый SUID-файл'
        CRON_CHANGED = 'cron_changed', 'Изменение cron'
        NEW_PORT = 'new_port', 'Новый порт'
        DISK_FULL = 'disk_full', 'Диск заполнен'
        KERNEL_ERROR = 'kernel_error', 'Ошибка ядра'
        INVENTORY = 'inventory', 'Инвентаризация'
        AGENT_ALIVE = 'agent_alive', 'Агент жив'
        ABSENCE_LOGIN = 'absence_login', 'Вход в период отсутствия'
        LOGIN = 'login', 'Вход пользователя'
        LOGINS_2D = 'logins_2d', 'История входов за 2 дня'
        LOGINS_MONTH = 'logins_month', 'История входов за месяц'
        UPDATES_PENDING = 'updates_pending', 'Ожидают обновления'
        BROWSER_HISTORY = 'browser_history', 'История браузеров'
        PACKAGES_MODIFIED = 'packages_modified', 'Изменены пакеты'
        # Normal mode
        SUDO_FAILED = 'sudo_failed', 'Неудачный sudo'
        PARSEC_EVENTS = 'parsec_events', 'События Parsec'
        ACCOUNT_CHANGED = 'account_changed', 'Изменение учётной записи'
        SUSPICIOUS_PROCESS = 'suspicious_process', 'Подозрительный процесс'
        # Hourly mode
        NEW_CONNECTION = 'new_connection', 'Новое соединение'
        FIREWALL_CHANGED = 'firewall_changed', 'Изменение фаервола'
        NEW_DEVICE = 'new_device', 'Новое устройство'
        SCREEN_LOCK_LOG = 'screen_lock_log', 'Журнал блокировок экрана'
        LOGIN_UNKNOWN = 'login_unknown', 'Неизвестный пользователь'

    host = models.ForeignKey(
        Host, on_delete=models.CASCADE, related_name='events',
        verbose_name='Хост',
    )
    event_type = models.CharField(
        'Тип события', max_length=50,
        choices=EventType.choices,
        db_index=True,
    )
    severity = models.CharField(
        'Серьёзность', max_length=10,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    message = models.TextField('Сообщение')
    details = models.JSONField('Детали', default=dict, blank=True)
    occurred_at = models.DateTimeField('Время события', db_index=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Событие безопасности'
        verbose_name_plural = 'События безопасности'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['event_type', 'occurred_at']),
            models.Index(fields=['host', 'occurred_at']),
            models.Index(fields=['severity', 'occurred_at']),
        ]

    def __str__(self):
        sev = dict(self.Severity.choices).get(self.severity, self.severity)
        return f"[{sev}] {self.host.hostname} — {self.get_event_type_display()}"


# ============================================================================
# Отпуска / больничные / командировки
# ============================================================================

class LeaveType(models.TextChoices):
    VACATION = 'vacation', 'Отпуск'
    SICK_LEAVE = 'sick_leave', 'Больничный'
    BUSINESS_TRIP = 'business_trip', 'Командировка'
    UNPAID_LEAVE = 'unpaid_leave', 'Без содержания'
    EDUCATIONAL_LEAVE = 'educational_leave', 'Учебный отпуск'


class EmployeeLeave(models.Model):
    """Период отсутствия сотрудника (отпуск, больничный, командировка)."""

    employee = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE,
        related_name='leaves', verbose_name='Сотрудник',
    )
    leave_type = models.CharField(
        'Тип отсутствия', max_length=20,
        choices=LeaveType.choices,
    )
    start_date = models.DateField('Дата начала')
    end_date = models.DateField('Дата окончания')
    reason = models.TextField('Причина / комментарий', blank=True)
    is_approved = models.BooleanField('Согласовано', default=False)
    approved_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_leaves',
        verbose_name='Согласовал',
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Отсутствие сотрудника'
        verbose_name_plural = 'Отсутствия сотрудников'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['employee', 'start_date', 'end_date']),
        ]

    def __str__(self):
        type_label = dict(LeaveType.choices).get(self.leave_type, self.leave_type)
        return f"{self.employee} — {type_label} ({self.start_date} — {self.end_date})"

    def is_active(self):
        """Проверка, действует ли отсутствие прямо сейчас."""
        now = timezone.now().date()
        return self.start_date <= now <= self.end_date and self.is_approved

    def contains_date(self, date):
        """Проверяет, попадает ли дата в период отсутствия."""
        if isinstance(date, timezone.datetime):
            date = date.date()
        return self.start_date <= date <= self.end_date


# ============================================================================
# Алерты: вход в период отсутствия
# ============================================================================

class AbsenceAlert(models.Model):
    """Алерт: сотрудник вошёл в систему в период отсутствия."""

    employee = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE,
        related_name='absence_alerts', verbose_name='Сотрудник',
    )
    leave = models.ForeignKey(
        EmployeeLeave, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alerts',
        verbose_name='Период отсутствия',
    )
    host = models.ForeignKey(
        Host, on_delete=models.CASCADE, related_name='absence_alerts',
        verbose_name='Хост',
    )
    login_time = models.DateTimeField('Время входа', db_index=True)
    username = models.CharField('Имя пользователя', max_length=100)
    domain_account = models.CharField('Доменная учётная запись', max_length=100, blank=True)
    is_acknowledged = models.BooleanField('Подтверждено', default=False)
    acknowledged_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='acknowledged_alerts',
        verbose_name='Подтвердил',
    )
    acknowledged_at = models.DateTimeField('Время подтверждения', null=True, blank=True)
    notes = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Алерт отсутствия'
        verbose_name_plural = 'Алерты отсутствия'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'created_at']),
            models.Index(fields=['is_acknowledged', 'created_at']),
        ]

    def __str__(self):
        type_label = dict(LeaveType.choices).get(self.leave.leave_type, self.leave.leave_type) if self.leave else 'Неизвестно'
        return f"{self.employee} — {type_label} — {self.login_time:%Y-%m-%d %H:%M}"
