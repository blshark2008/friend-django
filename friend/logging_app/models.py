from django.db import models
from django.utils import timezone


class LogEntry(models.Model):
    """Журналирование операций и событий системы."""

    class Severity(models.TextChoices):
        INFO = "info", "Информация"
        WARNING = "warning", "Предупреждение"
        ERROR = "error", "Ошибка"
        CRITICAL = "critical", "Критическое"

    class Action(models.TextChoices):
        CREATE = "create", "Создание"
        UPDATE = "update", "Изменение"
        DELETE = "delete", "Удаление"
        RESTORE = "restore", "Восстановление"
        ARCHIVE = "archive", "Архивирование"
        GRANT = "grant", "Предоставление доступа"
        REVOKE = "revoke", "Отозвать доступ"
        APPROVE = "approve", "Согласование"
        REJECT = "reject", "Отклонение"
        LOGIN = "login", "Вход в систему"
        LOGOUT = "logout", "Выход из системы"
        API_CALL = "api_call", "API запрос"
        CUSTOM = "custom", "Пользовательское"

    source = models.CharField(
        'Источник', max_length=50, blank=True, default='',
        help_text='Модуль системы: access, accounts, equipment, siem, custom',
    )
    action = models.CharField(
        'Действие', max_length=20, choices=Action.choices, default=Action.CUSTOM,
    )
    severity = models.CharField(
        'Серьёзность', max_length=10, choices=Severity.choices, default=Severity.INFO,
    )
    actor = models.CharField(
        'Исполнитель', max_length=255, blank=True, default='',
        help_text='Пользователь или система, выполнившая действие',
    )
    actor_type = models.CharField(
        'Тип исполнителя', max_length=20, blank=True, default='',
        choices=[
            ('user', 'Пользователь'),
            ('system', 'Система'),
            ('api', 'API'),
            ('service', 'Сервис'),
        ],
    )
    target_model = models.CharField(
        'Модель', max_length=100, blank=True, default='',
        help_text='Название модели: AccessGroup, Resource, AccessGrant и т.д.',
    )
    target_id = models.PositiveIntegerField(
        'ID объекта', null=True, blank=True,
        help_text='ID записи в целевой модели',
    )
    target_display = models.CharField(
        'Наименование объекта', max_length=500, blank=True, default='',
        help_text='Отображаемое имя целевого объекта',
    )
    summary = models.TextField(
        'Сводка', blank=True, default='',
        help_text='Краткое описание события',
    )
    details = models.JSONField(
        'Детали', blank=True, default=dict,
        help_text='Полная информация об изменении (old/new values)',
    )
    ip_address = models.GenericIPAddressField(
        'IP-адрес', null=True, blank=True,
    )
    user_agent = models.TextField(
        'User-Agent', blank=True, default='',
    )
    timestamp = models.DateTimeField(
        'Время события', auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Запись журнала'
        verbose_name_plural = 'Журнал операций'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['source', 'timestamp']),
            models.Index(fields=['target_model', 'target_id']),
            models.Index(fields=['severity']),
        ]

    def __str__(self):
        return f'{self.timestamp.strftime("%d.%m.%Y %H:%M")} [{self.get_severity_display()}] {self.actor} {self.action} {self.target_display}'

    @property
    def is_recent(self):
        """Событие произошло в последние 5 минут."""
        return (timezone.now() - self.timestamp).total_seconds() < 300

    @property
    def is_warning_or_higher(self):
        """Серьёзность >= warning."""
        return self.severity in [
            self.Severity.WARNING,
            self.Severity.ERROR,
            self.Severity.CRITICAL,
        ]
