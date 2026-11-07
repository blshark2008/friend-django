from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType

from accounts.models import Department


class TrainingType(models.Model):
    """Тип обучения (например: «Охрана труда», «Пожарная безопасность» и т.д.)"""

    name = models.CharField('Название', max_length=255, db_index=True)
    description = models.TextField('Описание', blank=True)
    skillspace_course_id = models.IntegerField(
        'ID курса на Skillspace', blank=True, null=True,
        help_text='ID курса на платформе skillspace.ru',
    )
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Тип обучения'
        verbose_name_plural = 'Типы обучения'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def active_trainings_count(self):
        """Количество активных назначений обучения этого типа."""
        return self.trainings.filter(is_active=True).count()

    @property
    def total_enrollments(self):
        """Общее количество сотрудников, назначенных на этот тип обучения."""
        return self.trainings.aggregate(
            total=models.Count('enrollments')
        )['total'] or 0

    @property
    def completed_count(self):
        """Количество сотрудников, прошедших обучение."""
        return self.trainings.filter(
            enrollments__status='completed'
        ).distinct().count()

    @property
    def not_completed_count(self):
        """Количество сотрудников, не прошедших обучение."""
        return self.trainings.filter(
            enrollments__status__in=['not_started', 'in_progress', 'failed']
        ).distinct().count()


class Training(models.Model):
    """Назначение конкретного типа обучения сотрудникам."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает запуска'
        ACTIVE = 'active', 'Активно'
        COMPLETED = 'completed', 'Завершено'
        ARCHIVED = 'archived', 'Архивировано'

    training_type = models.ForeignKey(
        TrainingType, on_delete=models.CASCADE, related_name='trainings',
        verbose_name='Тип обучения',
    )
    title = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    status = models.CharField(
        'Статус', max_length=20, choices=Status.choices, default=Status.PENDING,
        db_index=True,
    )
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='TrainingEnrollment',
        related_name='trainings', verbose_name='Сотрудники',
    )
    start_date = models.DateField('Дата начала', blank=True, null=True)
    end_date = models.DateField('Дата окончания', blank=True, null=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    last_sync_at = models.DateTimeField('Последняя синхронизация', blank=True, null=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Обучение'
        verbose_name_plural = 'Обучения'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['training_type', 'status']),
        ]

    def __str__(self):
        return f'{self.training_type} — {self.title}'

    @property
    def total_enrollments(self):
        return self.enrollments.count()

    @property
    def completed_count(self):
        return self.enrollments.filter(status='completed').count()

    @property
    def not_completed_count(self):
        return self.enrollments.filter(
            status__in=['not_started', 'in_progress', 'failed']
        ).count()

    @property
    def completion_rate(self):
        if not self.total_enrollments:
            return 0
        return round(self.completed_count / self.total_enrollments * 100)

    def sync_to_skillspace(self):
        """Sync enrollments to Skillspace platform."""
        from training.services.skillspace_api import SkillspaceClient, SkillspaceAPIError

        if not self.training_type.skillspace_course_id:
            raise SkillspaceAPIError('Не указан ID курса на Skillspace')

        client = SkillspaceClient()
        added = []
        errors = []

        for enrollment in self.enrollments.filter(status='not_started'):
            user = enrollment.user
            if not user.corporate_email and not user.personal_email:
                errors.append(f'{user.get_full_name()} — нет email')
                continue

            email = user.corporate_email or user.personal_email
            try:
                client.add_student_to_course(
                    self.training_type.skillspace_course_id,
                    email,
                    user.first_name,
                    user.last_name,
                )
                enrollment.status = 'in_progress'
                enrollment.skillspace_student_id = f'{user.id}'
                enrollment.save(update_fields=['status', 'skillspace_student_id'])
                added.append(user.get_full_name())
            except SkillspaceAPIError as e:
                errors.append(f'{user.get_full_name()}: {str(e)}')
                logger.error(f'Failed to sync {user.get_full_name()}: {e}')

        self.last_sync_at = timezone.now()
        self.status = self.Status.ACTIVE
        self.save(update_fields=['last_sync_at', 'status'])

        return {'added': added, 'errors': errors}

    def sync_from_skillspace(self):
        """Fetch completion data from Skillspace and update enrollments."""
        from training.services.skillspace_api import SkillspaceClient, SkillspaceAPIError

        if not self.training_type.skillspace_course_id:
            raise SkillspaceAPIError('Не указан ID курса на Skillspace')

        client = SkillspaceClient()
        updated = []
        errors = []

        for enrollment in self.enrollments.all():
            user = enrollment.user
            email = user.corporate_email or user.personal_email
            if not email:
                continue

            try:
                progress = client.get_course_progress(
                    self.training_type.skillspace_course_id, email
                )

                # Determine status from progress data
                is_completed = progress.get('completed', False)
                is_failed = progress.get('failed', False)
                score = progress.get('score', 0)
                completed_at = progress.get('completed_at')

                if is_completed:
                    enrollment.status = 'completed'
                    enrollment.score = score
                    if completed_at:
                        enrollment.completed_at = timezone.make_aware(
                            timezone.datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        )
                elif is_failed:
                    enrollment.status = 'failed'
                    enrollment.score = score
                else:
                    enrollment.status = 'in_progress'

                enrollment.save(update_fields=['status', 'score', 'completed_at'])
                updated.append(user.get_full_name())
            except SkillspaceAPIError as e:
                errors.append(f'{user.get_full_name()}: {str(e)}')

        self.last_sync_at = timezone.now()
        self.save(update_fields=['last_sync_at'])

        return {'updated': updated, 'errors': errors}

    def get_not_completed(self):
        """Get users who haven't completed the training."""
        return self.enrollments.filter(
            status__in=['not_started', 'in_progress', 'failed']
        ).select_related('user', 'user__department')

    def get_completed(self):
        """Get users who completed the training."""
        return self.enrollments.filter(
            status='completed'
        ).select_related('user', 'user__department')


class TrainingEnrollment(models.Model):
    """Назначение конкретного сотрудника на конкретное обучение."""

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'Не начато'
        IN_PROGRESS = 'in_progress', 'В процессе'
        COMPLETED = 'completed', 'Пройдено'
        FAILED = 'failed', 'Не пройдено'

    training = models.ForeignKey(
        Training, on_delete=models.CASCADE, related_name='enrollments',
        verbose_name='Обучение',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='training_enrollments',
        verbose_name='Сотрудник',
    )
    status = models.CharField(
        'Статус', max_length=20, choices=Status.choices, default=Status.NOT_STARTED,
        db_index=True,
    )
    score = models.FloatField('Оценка/балл', blank=True, null=True, help_text='Результат тестирования')
    skillspace_student_id = models.CharField(
        'ID студента на Skillspace', max_length=100, blank=True,
    )
    enrolled_at = models.DateTimeField('Дата назначения', auto_now_add=True)
    completed_at = models.DateTimeField('Дата прохождения', blank=True, null=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Назначение обучения'
        verbose_name_plural = 'Назначения обучения'
        unique_together = ['training', 'user']
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f'{self.user.get_full_name()} — {self.training}'

    @property
    def status_label(self):
        return dict(self.Status.choices).get(self.status, self.status)
