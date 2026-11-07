"""
Webhook-эндпоинт для приёма сообщений от MAX.

Формат входящего JSON (объект Update):
{
    "update_type": "message_created",
    "timestamp": 1234567890,
    "message": {
        "sender": {
            "user_id": 15284524,
            "first_name": "Иван",
            "last_name": "Иванов",
            "is_bot": false
        },
        "recipient": {
            "chat_type": "dialog",
            "chat_id": 382781738,
            "user_id": 372895750
        },
        "body": {
            "text": "/register"
        }
    }
}
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from messaging.bots.max_bot import handle_command, handle_message, session_store
from messaging.services.max_api import MAXClient, MAXAPIError

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def max_webhook(request):
    """
    Webhook для приёма событий от MAX.
    """
    # Проверка секретного ключа
    secret = getattr(settings, 'MAX_WEBHOOK_SECRET', '')
    if secret:
        received_secret = request.headers.get('X-Max-Bot-Api-Secret', '')
        if received_secret != secret:
            logger.warning('Webhook: неверный secret ключ')
            return JsonResponse({'status': 'error', 'message': 'Invalid secret'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f'JSON decode error: {e}')
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    update_type = data.get('update_type', '')
    message_data = data.get('message', {})
    sender_data = message_data.get('sender', {})
    recipient_data = message_data.get('recipient', {})
    body_data = message_data.get('body', {})

    # user_id — кто отправил
    user_id = sender_data.get('user_id')
    if not user_id:
        logger.warning('Webhook: отсутствует sender.user_id')
        return JsonResponse({'status': 'ok'})

    # Пропускаем события от ботов
    if sender_data.get('is_bot'):
        return JsonResponse({'status': 'ok'})

    # chat_id — куда отвечать
    chat_id = recipient_data.get('chat_id')
    message_text = body_data.get('text', '').strip()

    if not message_text:
        return JsonResponse({'status': 'ok'})

    logger.info(f'Webhook: update_type={update_type}, user_id={user_id}, chat_id={chat_id}, text={message_text[:100]}')

    # Обработка команд
    response_text = None
    if message_text.startswith('/'):
        parts = message_text.split(' ', 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ''
        response_text = handle_command(user_id, command, args)
    else:
        response_text = handle_message(user_id, message_text)

    if response_text:
        try:
            client = MAXClient()
            if chat_id:
                client.send_message(chat_id=chat_id, text=response_text)
            else:
                client.send_message(user_id=user_id, text=response_text)
            logger.info(f'Webhook: ответ отправлен пользователю {user_id}')
        except MAXAPIError as e:
            logger.error(f'Webhook: ошибка отправки ответа: {e}')

    return JsonResponse({'status': 'ok'})
