from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
import logging

from accounts.models import Department


logger = logging.getLogger(__name__)


class TrainingGoal(models.Model):
    """Цель обучения (например: пожарная безопасность, информационная безопасность, охрана труда)."""

    name = models.CharField('Название', max_length=255, db_index=True)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    # Обучения (типы), которые относятся к этой цели
    training_types = models.ManyToManyField(
        'TrainingType', through='GoalTrainingType',
        related_name='goals', verbose_name='Обучающие курсы',
    )

    class Meta:
        verbose_name = 'Цель обучения'
        verbose_name_plural = 'Цели обучения'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def training_types_count(self):
        """Количество обучающих курсов, привязанных к этой цели."""
        return self.training_types.count()


class GoalTrainingType(models.Model):
    """Связь цели обучения с типом обучения (промежуточная таблица)."""

    goal = models.ForeignKey(
        TrainingGoal, on_delete=models.CASCADE, related_name='_goal_training_types',
        verbose_name='Цель обучения',
    )
    training_type = models.ForeignKey(
        'TrainingType', on_delete=models.CASCADE, related_name='_goal_type_links',
        verbose_name='Обучающий курс',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Связь цели и курса'
        verbose_name_plural = 'Связи целей и курсов'
        unique_together = ['goal', 'training_type']

    def __str__(self):
        return f'{self.goal.name} — {self.training_type.name}'


class TrainingCategory(models.Model):
    """Категория типа обучения (например: информационная безопасность, пожарная безопасность и т.д.)"""

    name = models.CharField('Название', max_length=255, db_index=True)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Категория обучения'
        verbose_name_plural = 'Категории обучения'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def training_types_count(self):
        """Количество обучающих курсов в этой категории."""
        return self.training_types.filter(is_active=True).count()


class TrainingType(models.Model):
    """Обучающий курс (например: «Охрана труда», «Пожарная безопасность» и т.д.)"""

    category = models.ForeignKey(
        TrainingCategory, on_delete=models.SET_NULL, related_name='training_types',
        verbose_name='Категория', null=True, blank=True,
    )
    name = models.CharField('Название', max_length=255, db_index=True)
    description = models.TextField('Описание', blank=True)
    skillspace_course_id = models.CharField(
        'UUID курса на Skillspace', max_length=100, blank=True, default='',
        help_text='UUID курса на платформе skillspace.ru',
    )
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Обучающий курс'
        verbose_name_plural = 'Обучающие курсы'
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
        verbose_name='Обучающий курс',
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
        through_fields=('training', 'user'),
    )
    start_date = models.DateField('Дата начала', blank=True, null=True)
    end_date = models.DateField('Дата окончания', blank=True, null=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    last_sync_at = models.DateTimeField('Последняя синхронизация', blank=True, null=True)
    is_active = models.BooleanField('Активен', default=True)
    group = models.ForeignKey(
        'SkillspaceGroup', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='trainings', verbose_name='Группа на Skillspace',
    )

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
            group_id = enrollment.group.skillspace_id if enrollment.group else ''
            try:
                client.invite_student(
                    email=email,
                    course_id=self.training_type.skillspace_course_id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    patronymic=user.patronymic,
                    comment=f"Табельный номер: {user.tab_number}" if user.tab_number else '',
                    disable_notification=True,
                    group_id=group_id,
                )
                enrollment.status = 'in_progress'
                enrollment.display_status = TrainingEnrollment.DisplayStatus.COURSE_STARTED
                enrollment.skillspace_student_id = f'{user.id}'
                enrollment.save(update_fields=['status', 'display_status', 'skillspace_student_id'])
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
                    enrollment.display_status = TrainingEnrollment.DisplayStatus.COMPLETED_SUCCESS
                    enrollment.score = score
                    if completed_at:
                        enrollment.completed_at = timezone.make_aware(
                            timezone.datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        )
                elif is_failed:
                    enrollment.status = 'failed'
                    enrollment.display_status = TrainingEnrollment.DisplayStatus.FAILED_STATUS
                    enrollment.score = score
                else:
                    enrollment.status = 'in_progress'
                    enrollment.display_status = TrainingEnrollment.DisplayStatus.COURSE_STARTED

                enrollment.save(update_fields=['status', 'display_status', 'score', 'completed_at'])
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


class SkillspaceGroup(models.Model):
    """Группа на платформе Skillspace."""

    course = models.ForeignKey(
        TrainingType, on_delete=models.CASCADE, related_name='skillspace_groups',
        verbose_name='Курс',
    )
    skillspace_id = models.CharField(
        'ID на Skillspace', max_length=100, db_index=True,
    )
    name = models.CharField('Название', max_length=255)
    students_count = models.PositiveIntegerField('Кол-во студентов', default=0)
    last_synced = models.DateTimeField('Последняя синхронизация', blank=True, null=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Группа Skillspace'
        verbose_name_plural = 'Группы Skillspace'
        unique_together = ['course', 'skillspace_id']
        ordering = ['name']

    def __str__(self):
        return f'{self.course.name} — {self.name}'

    @classmethod
    def sync_from_api(cls, course_id):
        """Sync groups from Skillspace API for a specific course."""
        from training.services.skillspace_api import SkillspaceClient, SkillspaceAPIError
        
        try:
            client = SkillspaceClient()
            groups_data = client.get_groups_by_course(course_id)
            
            # Find the TrainingType by course_id
            training_type = TrainingType.objects.filter(
                skillspace_course_id=course_id
            ).first()
            
            if not training_type:
                logger.warning(f'TrainingType not found for course_id {course_id}')
                return 0
            
            synced = 0
            for g in groups_data:
                cls.objects.update_or_create(
                    course=training_type,
                    skillspace_id=g['id'],
                    defaults={
                        'name': g.get('name', ''),
                        'students_count': g.get('studentsCount', 0),
                        'last_synced': timezone.now(),
                    }
                )
                synced += 1
            
            return synced
        except SkillspaceAPIError as e:
            logger.error(f'Failed to sync groups for course {course_id}: {e}')
            return 0

    @classmethod
    def sync_all_courses(cls):
        """Sync groups for all courses."""
        total = 0
        for tt in TrainingType.objects.filter(skillspace_course_id__isnull=False):
            total += cls.sync_from_api(tt.skillspace_course_id)
        return total


class TrainingEnrollment(models.Model):
    """Назначение конкретного сотрудника на конкретное обучение."""

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'Не начато'
        IN_PROGRESS = 'in_progress', 'В процессе'
        COMPLETED = 'completed', 'Пройдено'
        FAILED = 'failed', 'Не пройдено'

    class DisplayStatus(models.TextChoices):
        IN_LIST = 'in_list', 'В списке'
        ASSIGNED = 'assigned', 'Назначено'
        COURSE_STARTED = 'course_started', 'Начато'
        COMPLETED_SUCCESS = 'completed_success', 'Успешно завершено'
        FAILED_STATUS = 'failed_status', 'Не пройдено'

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
    display_status = models.CharField(
        'Отображаемый статус', max_length=20, choices=DisplayStatus.choices,
        default=DisplayStatus.IN_LIST, db_index=True,
    )
    score = models.FloatField('Оценка/балл', blank=True, null=True, help_text='Результат тестирования')
    skillspace_student_id = models.CharField(
        'ID студента на Skillspace', max_length=100, blank=True,
    )
    group = models.ForeignKey(
        'SkillspaceGroup', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='enrollments', verbose_name='Группа на Skillspace',
    )
    enrolled_at = models.DateTimeField('Дата назначения', auto_now_add=True)
    completed_at = models.DateTimeField('Дата прохождения', blank=True, null=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        blank=True, null=True, related_name='assigned_trainings',
        verbose_name='Назначил',
    )
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

    @property
    def display_status_label(self):
        return dict(self.DisplayStatus.choices).get(self.display_status, self.display_status)

    def save(self, *args, **kwargs):
        # Sync display_status based on status and skillspace data
        if self.status == 'completed':
            self.display_status = self.DisplayStatus.COMPLETED_SUCCESS
        elif self.status == 'failed':
            self.display_status = self.DisplayStatus.FAILED_STATUS
        elif self.status == 'in_progress':
            if self.skillspace_student_id:
                self.display_status = self.DisplayStatus.COURSE_STARTED
            else:
                self.display_status = self.DisplayStatus.ASSIGNED
        else:
            self.display_status = self.DisplayStatus.IN_LIST
        super().save(*args, **kwargs)
