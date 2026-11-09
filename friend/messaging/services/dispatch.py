"""
Служба отправки сообщений пользователям.

Отправляет сообщения через MAX, Telegram или Email.
"""

import logging
from datetime import datetime

from messaging.models import Message, MessageRecipient

logger = logging.getLogger(__name__)


def dispatch_message(message: Message) -> dict:
    """
    Отправляет сообщение всем получателям.
    Возвращает словарь с результатами: {"delivered": N, "failed": N}.
    """
    results = {'delivered': 0, 'failed': 0}

    recipients = message.recipients.filter(
        delivery_status=MessageRecipient.STATUS_PENDING
    )

    for recipient in recipients:
        try:
            delivered = _send_to_channel(message, recipient)
            if delivered:
                recipient.delivery_status = MessageRecipient.STATUS_DELIVERED
                recipient.delivered_at = datetime.now()
                recipient.save()
                results['delivered'] += 1
            else:
                raise Exception('Delivery returned False')
        except Exception as e:
            logger.error(
                f'Ошибка отправки {message.id} пользователю {recipient.recipient_id} '
                f'через {recipient.delivery_channel}: {e}',
                exc_info=True,
            )
            recipient.delivery_status = MessageRecipient.STATUS_FAILED
            recipient.error_message = str(e)[:500]
            recipient.save()
            results['failed'] += 1

    # Обновляем статус сообщения
    all_delivered = recipients.filter(
        delivery_status__in=[MessageRecipient.STATUS_DELIVERED, MessageRecipient.STATUS_READ]
    ).count() == recipients.count() if recipients.exists() else True

    if all_delivered and results['failed'] == 0:
        message.status = Message.STATUS_SENT
    elif results['failed'] > 0 and results['delivered'] == 0:
        message.status = Message.STATUS_FAILED
        message.error_message = 'Не удалось доставить ни одного сообщения'

    message.sent_at = datetime.now()
    message.save()

    return results


def _send_to_channel(message: Message, recipient: MessageRecipient) -> bool:
    """Отправляет сообщение через указанный канал."""
    channel = recipient.delivery_channel
    user = recipient.recipient

    if channel == Message.CHANNEL_MAX:
        return _send_via_max(message, user)
    elif channel == Message.CHANNEL_TELEGRAM:
        return _send_via_telegram(message, user)
    elif channel == Message.CHANNEL_EMAIL_CORPORATE:
        return _send_via_email(message, user.corporate_email)
    elif channel == Message.CHANNEL_EMAIL_PERSONAL:
        return _send_via_email(message, user.personal_email)

    return False


def _send_via_max(message: Message, user) -> bool:
    """Отправка через MAX API."""
    from messaging.services.max_api import MAXClient, MAXAPIError

    if not user.max_id:
        raise MAXAPIError(f'У пользователя {user.get_full_name()} (tab={user.tab_number}) не указан max_id')

    try:
        client = MAXClient()
        # user_id в MAX — это integer
        user_id_int = int(user.max_id) if user.max_id.isdigit() else None
        if user_id_int:
            client.send_message(
                user_id=user_id_int,
                text=f"{message.title or ''}\n\n{message.content}",
                format='html',
            )
        else:
            logger.warning(f'MAX: user_id не числовой: {user.max_id}')
            return False
        logger.info(f'MAX: Отправка "{message.title}" пользователю {user.get_full_name()} (tab={user.tab_number}, max_id={user_id_int})')
        return True
    except MAXAPIError as e:
        raise Exception(f'MAX API error: {e}')


def _send_via_telegram(message: Message, user) -> bool:
    """Отправка через Telegram Bot API."""
    if not user.telegram_id:
        return False

    from django.conf import settings
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        logger.warning('TELEGRAM_BOT_TOKEN не настроен')
        return False

    # TODO: Реализовать отправку через Telegram Bot API
    # from telebot import TeleBot
    # bot = TeleBot(token)
    # bot.send_message(user.telegram_id, f'{message.title}\n\n{message.content}')
    logger.info(f'Telegram: Отправка "{message.title}" пользователю {user.tab_number}')
    return True


def _send_via_email(message: Message, email: str) -> bool:
    """Отправка через email."""
    if not email:
        return False

    from django.core.mail import send_mail
    from django.conf import settings

    subject = message.title or 'Сообщение от администрации НИИ КПССЗ'
    try:
        send_mail(
            subject=subject,
            message=message.content,
            from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@friend.local',
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f'Email: Отправка "{message.title}" на {email}')
        return True
    except Exception as e:
        logger.error(f'Email ошибка отправки на {email}: {e}')
        return False
