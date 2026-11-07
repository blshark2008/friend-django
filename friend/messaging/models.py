from django.db import models
from django.conf import settings
from django.utils import timezone


class Message(models.Model):
    """Отправленное сообщение пользователю/группе/подразделению."""

    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Низкий'),
        (PRIORITY_NORMAL, 'Обычный'),
        (PRIORITY_HIGH, 'Высокий'),
        (PRIORITY_URGENT, 'Срочный'),
    ]

    # Каналы отправки
    CHANNEL_MAX = 'max'
    CHANNEL_TELEGRAM = 'telegram'
    CHANNEL_EMAIL_CORPORATE = 'email_corporate'
    CHANNEL_EMAIL_PERSONAL = 'email_personal'

    CHANNEL_CHOICES = [
        (CHANNEL_MAX, 'MAX'),
        (CHANNEL_TELEGRAM, 'Telegram'),
        (CHANNEL_EMAIL_CORPORATE, 'Корпоративная почта'),
        (CHANNEL_EMAIL_PERSONAL, 'Личная почта'),
    ]

    # Статусы
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_PENDING = 'pending'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Черновик'),
        (STATUS_PENDING, 'В очереди'),
        (STATUS_SENT, 'Отправлено'),
        (STATUS_FAILED, 'Ошибка отправки'),
    ]

    title = models.CharField('Заголовок', max_length=255, blank=True)
    content = models.TextField('Содержание')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Отправитель',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_messages',
    )
    priority = models.CharField(
        'Приоритет',
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL,
    )
    channel = models.CharField(
        'Канал отправки',
        max_length=30,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_MAX,
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    sent_at = models.DateTimeField('Отправлено', null=True, blank=True)
    error_message = models.TextField('Сообщение об ошибке', blank=True, default='')

    # Для рассылки по подразделению
    department = models.ForeignKey(
        'accounts.Department',
        verbose_name='Подразделение',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
    )

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['channel', 'status']),
            models.Index(fields=['department', 'status']),
        ]

    def __str__(self):
        return f"{self.title or self.content[:50]}... ({self.get_status_display()})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('messaging:message_detail', kwargs={'pk': self.pk})

    @property
    def recipient_count(self):
        """Общее количество получателей."""
        return self.recipients.count()

    @property
    def delivered_count(self):
        """Количество успешно доставленных."""
        return self.recipients.filter(delivery_status=MessageRecipient.STATUS_DELIVERED).count()


class MessageRecipient(models.Model):
    """Индивидуальная история доставки для каждого получателя."""

    STATUS_PENDING = 'pending'
    STATUS_DELIVERED = 'delivered'
    STATUS_FAILED = 'failed'
    STATUS_READ = 'read'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'В очереди'),
        (STATUS_DELIVERED, 'Доставлено'),
        (STATUS_FAILED, 'Не доставлено'),
        (STATUS_READ, 'Прочитано'),
    ]

    message = models.ForeignKey(
        Message,
        verbose_name='Сообщение',
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Получатель',
        on_delete=models.CASCADE,
        related_name='received_messages',
    )
    delivery_channel = models.CharField(
        'Канал доставки',
        max_length=30,
        choices=Message.CHANNEL_CHOICES,
    )
    delivery_status = models.CharField(
        'Статус доставки',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    sent_at = models.DateTimeField('Отправлено', null=True, blank=True)
    delivered_at = models.DateTimeField('Доставлено', null=True, blank=True)
    read_at = models.DateTimeField('Прочитано', null=True, blank=True)
    error_message = models.TextField('Ошибка', blank=True, default='')

    class Meta:
        verbose_name = 'Получатель сообщения'
        verbose_name_plural = 'Получатели сообщений'
        unique_together = ['message', 'recipient', 'delivery_channel']
        indexes = [
            models.Index(fields=['delivery_status', 'delivery_channel']),
        ]

    def __str__(self):
        return f"{self.recipient.get_full_name()} — {self.message.title or 'Без заголовка'} ({self.get_delivery_status_display()})"
