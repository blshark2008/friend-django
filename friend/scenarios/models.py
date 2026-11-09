from django.db import models
from django.conf import settings
import json


# ============================================================================
# Справочники
# ============================================================================

class Category(models.Model):
    """Категория сценариев (тип события)."""
    name = models.CharField('Название', max_length=200, unique=True)
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return self.name


class Scenario(models.Model):
    """Сценарий оповещения."""
    category = models.ForeignKey(
        Category,
        verbose_name='Категория',
        on_delete=models.CASCADE,
        related_name='scenarios',
    )
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    version = models.IntegerField('Версия', default=1)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Сценарий'
        verbose_name_plural = 'Сценарии'
        ordering = ['category', 'name', 'version']
        unique_together = ['category', 'name', 'version']

    def __str__(self):
        return f'{self.name} v{self.version} ({self.category.name})'

    def save(self, *args, **kwargs):
        if not self.version:
            max_version = Scenario.objects.filter(
                category=self.category,
                name=self.name,
            ).count() + 1
            self.version = max_version
        super().save(*args, **kwargs)


class Branch(models.Model):
    """Ветка сценария (линия оповещения)."""
    scenario = models.ForeignKey(
        Scenario,
        verbose_name='Сценарий',
        on_delete=models.CASCADE,
        related_name='branches',
    )
    name = models.CharField('Название', max_length=200)
    code = models.CharField('Код', max_length=50, unique=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Ветка'
        verbose_name_plural = 'Ветки'
        ordering = ['scenario', 'code']

    def __str__(self):
        return f'{self.name} ({self.code}) — {self.scenario}'


class Step(models.Model):
    """Шаг ветки сценария."""
    branch = models.ForeignKey(
        Branch,
        verbose_name='Ветка',
        on_delete=models.CASCADE,
        related_name='steps',
    )
    prev_result_code = models.CharField(
        'Код результата предыдущего шага',
        max_length=100,
        blank=True,
        default='',
        help_text='Пусто для первого шага в ветке',
    )
    step_order = models.PositiveIntegerField(
        'Порядок',
        help_text='Порядок шага внутри ветки (при совпадении prev_result_code)',
    )
    message_text = models.TextField('Текст сообщения')
    message_json = models.JSONField(
        'JSON сбора ответа',
        default=dict,
        help_text='Тип сбора ответа: кнопки, число, текст, комбинированный',
    )
    mailing_list_json = models.JSONField(
        'Список рассылки',
        default=list,
        help_text='Роли/сотрудники/подразделения — получатели',
    )
    exclusion_list_json = models.JSONField(
        'Исключения',
        default=list,
        help_text='Исключения из рассылки',
    )
    db_write_json = models.JSONField(
        'Запись в базу',
        default=dict,
        help_text='Что записывать в базу при получении ответа',
    )
    deadline_min = models.PositiveIntegerField(
        'Дедлайн (мин)',
        default=0,
        help_text='0 — без дедлайна',
    )
    escalate_to_json = models.JSONField(
        'Эскалация',
        default=dict,
        help_text='Кому уведомить при просрочке',
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Шаг'
        verbose_name_plural = 'Шаги'
        ordering = ['branch', 'step_order', 'prev_result_code']
        unique_together = ['branch', 'step_order', 'prev_result_code']

    def __str__(self):
        return f'Шаг {self.step_order} [{self.prev_result_code or "первый"}] — {self.branch}'


# ============================================================================
# Исполнение
# ============================================================================

class Run(models.Model):
    """Запуск сценария."""
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидание'),
        (STATUS_RUNNING, 'Выполняется'),
        (STATUS_COMPLETED, 'Завершён'),
        (STATUS_CANCELLED, 'Отменён'),
    ]

    scenario = models.ForeignKey(
        Scenario,
        verbose_name='Сценарий',
        on_delete=models.CASCADE,
        related_name='runs',
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Запустил',
        on_delete=models.SET_NULL,
        null=True,
        related_name='scenarios_started',
    )
    started_at = models.DateTimeField('Запущен', auto_now_add=True)
    params_json = models.JSONField(
        'Параметры запуска',
        default=dict,
        help_text='Переменные контекста: {corpus}, {floor} и т.д.',
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    completed_at = models.DateTimeField('Завершён', null=True, blank=True)

    class Meta:
        verbose_name = 'Запуск'
        verbose_name_plural = 'Запуски'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.scenario} — {self.get_status_display()} ({self.started_at})'


class StepRun(models.Model):
    """Выполнение шага для конкретного пользователя."""
    STATUS_SENT = 'sent'
    STATUS_ANSWERED = 'answered'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_SENT, 'Отправлено'),
        (STATUS_ANSWERED, 'Ответ получен'),
        (STATUS_EXPIRED, 'Просрочено'),
        (STATUS_CANCELLED, 'Отменено'),
        (STATUS_FAILED, 'Ошибка отправки'),
    ]

    run = models.ForeignKey(
        Run,
        verbose_name='Запуск',
        on_delete=models.CASCADE,
        related_name='step_runs',
    )
    step = models.ForeignKey(
        Step,
        verbose_name='Шаг',
        on_delete=models.CASCADE,
        related_name='step_runs',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Получатель',
        on_delete=models.CASCADE,
        related_name='step_runs',
    )
    sent_at = models.DateTimeField('Отправлено', null=True, blank=True)
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SENT,
        db_index=True,
    )
    result_code = models.CharField(
        'Код результата',
        max_length=100,
        blank=True,
        default='',
    )
    deadline_at = models.DateTimeField('Дедлайн', null=True, blank=True)
    escalated_at = models.DateTimeField('Эскалация', null=True, blank=True)
    error_message = models.TextField('Ошибка отправки', blank=True, default='')

    class Meta:
        verbose_name = 'Выполнение шага'
        verbose_name_plural = 'Выполнения шагов'
        unique_together = ['run', 'step', 'recipient']

    def __str__(self):
        return f'{self.step.branch} → {self.recipient} ({self.get_status_display()})'


class Answer(models.Model):
    """Ответ пользователя на шаг."""
    run = models.ForeignKey(
        Run,
        verbose_name='Запуск',
        on_delete=models.CASCADE,
        related_name='answers',
    )
    step_run = models.ForeignKey(
        StepRun,
        verbose_name='Выполнение шага',
        on_delete=models.CASCADE,
        related_name='answers',
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Сотрудник',
        on_delete=models.CASCADE,
        related_name='answers',
    )
    answer_json = models.JSONField('Ответ', default=dict)
    received_at = models.DateTimeField('Получен', auto_now_add=True)

    class Meta:
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'
        ordering = ['-received_at']

    def __str__(self):
        return f'{self.employee} — {self.step_run.step} ({self.received_at})'


class DbValue(models.Model):
    """Значения, записанные из db_write_json."""
    run = models.ForeignKey(
        Run,
        verbose_name='Запуск',
        on_delete=models.CASCADE,
        related_name='db_values',
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Сотрудник',
        on_delete=models.CASCADE,
        related_name='db_values',
    )
    key = models.CharField('Ключ', max_length=200)
    value = models.TextField('Значение')

    class Meta:
        verbose_name = 'Значение БД'
        verbose_name_plural = 'Значения БД'
        unique_together = ['run', 'employee', 'key']

    def __str__(self):
        return f'{self.run} — {self.employee} — {self.key}'


class Log(models.Model):
    """Журнал событий (неизменяемый)."""
    EVENT_STEP_SENT = 'step_sent'
    EVENT_ANSWER_RECEIVED = 'answer_received'
    EVENT_DEADLINE_EXPIRED = 'deadline_expired'
    EVENT_ESCALATION = 'escalation'
    EVENT_RUN_STARTED = 'run_started'
    EVENT_RUN_COMPLETED = 'run_completed'

    EVENT_CHOICES = [
        (EVENT_STEP_SENT, 'Шаг отправлен'),
        (EVENT_ANSWER_RECEIVED, 'Ответ получен'),
        (EVENT_DEADLINE_EXPIRED, 'Дедлайн истёк'),
        (EVENT_ESCALATION, 'Эскалация'),
        (EVENT_RUN_STARTED, 'Запуск начат'),
        (EVENT_RUN_COMPLETED, 'Запуск завершён'),
    ]

    run = models.ForeignKey(
        Run,
        verbose_name='Запуск',
        on_delete=models.CASCADE,
        related_name='logs',
    )
    event_type = models.CharField(
        'Тип события',
        max_length=30,
        choices=EVENT_CHOICES,
        db_index=True,
    )
    payload_json = models.JSONField('Данные', default=dict)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Журнал'
        verbose_name_plural = 'Журнал'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.run} — {self.get_event_type_display()} ({self.created_at})'


# ============================================================================
# Сотрудники и роли
# ============================================================================

class Role(models.Model):
    """Роль сотрудника."""
    name = models.CharField('Название', max_length=100, unique=True)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'
        ordering = ['name']

    def __str__(self):
        return self.name


class EmployeeRole(models.Model):
    """Связь сотрудника с ролью."""
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Сотрудник',
        on_delete=models.CASCADE,
        related_name='employee_roles',
    )
    role = models.ForeignKey(
        Role,
        verbose_name='Роль',
        on_delete=models.CASCADE,
        related_name='employee_roles',
    )
    scope_department = models.ForeignKey(
        'accounts.Department',
        verbose_name='Подразделение (scope)',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_roles',
    )

    class Meta:
        verbose_name = 'Роль сотрудника'
        verbose_name_plural = 'Роли сотрудников'
        unique_together = ['employee', 'role', 'scope_department']

    def __str__(self):
        return f'{self.employee} — {self.role}'


# ============================================================================
# Группы рассылки сценариев
# ============================================================================

class ScenarioMailGroup(models.Model):
    """Группа рассылки для сценариев — набор пользователей и подразделений."""
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True, default='')
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name='Пользователи',
        blank=True,
        related_name='scenario_mail_groups',
    )
    departments = models.ManyToManyField(
        'accounts.Department',
        verbose_name='Подразделения',
        blank=True,
        related_name='scenario_mail_groups',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Создана',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_scenario_mail_groups',
    )
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Группа рассылки сценариев'
        verbose_name_plural = 'Группы рассылки сценариев'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        """Общее количество уникальных пользователей в группе."""
        from accounts.models import User
        direct_count = self.users.count()
        dept_users = User.objects.filter(
            department__in=self.departments.all(),
            archive_status=User.STATUS_ACTIVE,
        ).exclude(pk__in=self.users.all())
        return direct_count + dept_users.count()

    @property
    def user_ids(self):
        """Все ID пользователей в группе (без дублей)."""
        from accounts.models import User
        direct_ids = set(self.users.values_list('pk', flat=True))
        dept_ids = set(
            User.objects.filter(
                department__in=self.departments.all(),
                archive_status=User.STATUS_ACTIVE,
            ).values_list('pk', flat=True)
        )
        return direct_ids | dept_ids
