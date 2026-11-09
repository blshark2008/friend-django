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


def _extract_buttons_from_message_json(message_json):
    """Извлекает кнопки из message_json шага сценария."""
    if not isinstance(message_json, dict):
        return None
    msg_type = message_json.get('type', '')
    if msg_type not in ('buttons', 'buttons_with_number'):
        return None
    options = message_json.get('options', [])
    buttons = []
    for opt in options:
        buttons.append({
            'type': 'callback',
            'text': opt.get('text', ''),
            'payload': opt.get('result_code', ''),
        })
    return buttons if buttons else None

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
            return JsonResponse({'status': 'error', 'message': 'Invalid secret'}, status=403)

    data = json.loads(request.body)
    update_type = data.get('update_type', '')
    message_data = data.get('message', {})
    body_data = message_data.get('body', {})
    sender_data = message_data.get('sender', {})
    recipient_data = message_data.get('recipient', {})

    user_id = sender_data.get('user_id')
    chat_id = recipient_data.get('chat_id')
    message_text = body_data.get('text', '').strip()

    # Детальное логирование всех входящих webhook
    logger.info(f'Webhook IN: update_type={update_type}')
    logger.info(f'Webhook IN: full data keys={list(data.keys())}')
    logger.info(f'Webhook IN: message keys={list(message_data.keys())}')
    logger.info(f'Webhook IN: body keys={list(body_data.keys())}')
    logger.info(f'Webhook IN: sender={sender_data}')
    logger.info(f'Webhook IN: recipient={recipient_data}')
    logger.info(f'Webhook IN: full body_data={body_data}')
    
    if update_type in ('bot_callback', 'callback_query', 'callback'):
        logger.info(f'Webhook: callback event update_type={update_type}')
        # Callback payload может быть в разных полях
        callback_payload = (
            body_data.get('callback_data') or
            body_data.get('action', {}).get('value') or
            body_data.get('action', {}).get('payload') or
            data.get('callback_data') or
            data.get('payload')
        )
        logger.info(f'Webhook: extracted callback_payload={callback_payload}')
        if callback_payload:
            logger.info(f'Webhook: callback payload={callback_payload} from user {user_id}')
            from scenarios.services.executor import ScenarioExecutor
            from scenarios.models import Run, StepRun
            from accounts.models import User as AccountUser
            
            django_user = AccountUser.objects.filter(max_id=str(user_id)).first()
            if not django_user:
                logger.warning(f'Webhook: пользователь с MAX user_id={user_id} не найден в Django')
                return JsonResponse({'status': 'ok'})
            
            step_run = StepRun.objects.filter(
                recipient_id=django_user.pk,
                status=StepRun.STATUS_SENT,
            ).order_by('-step__step_order').first()
            
            if step_run:
                try:
                    run = step_run.run
                    executor = ScenarioExecutor(run)
                    result = executor.process_answer(
                        user_id=django_user.pk,
                        message_text='',
                        button_result_code=callback_payload,
                    )
                    logger.info(f'Webhook: callback processed: {result}')
                    
                    if result.get('success') and result.get('next_step_id'):
                        next_message = result.get('next_message', '')
                        if next_message:
                            try:
                                from scenarios.models import Step
                                next_step = Step.objects.filter(
                                    pk=result['next_step_id'],
                                    branch__scenario_id=result['scenario_id'],
                                ).first()
                                buttons = _extract_buttons_from_message_json(
                                    next_step.message_json if next_step else None
                                )
                                client = MAXClient()
                                client.send_message(chat_id=chat_id, text=next_message, buttons=buttons)
                                logger.info(f'Webhook: next step sent to user {django_user.pk}')
                            except MAXAPIError as e:
                                logger.error(f'Webhook: ошибка отправки следующего шага: {e}')
                except Exception as e:
                    logger.error(f'Webhook: ошибка обработки callback: {e}')
            else:
                logger.warning(f'Webhook: нет активного step_run для пользователя {django_user.pk}')
            
            return JsonResponse({'status': 'ok'})

    logger.info(f'Webhook: update_type={update_type}, user_id={user_id}, chat_id={chat_id}, text={message_text[:100]}')

    # Проверяем, является ли это нажатием кнопки
    # MAX отправляет callback через body с attachment или text
    callback_payload = None
    
    # 1. Проверяем body на наличие callback данных (callback_data или action)
    callback_data = body_data.get('callback_data')
    if callback_data:
        callback_payload = callback_data
    
    # 2. Проверяем body на наличие action
    action = body_data.get('action', {})
    if action:
        callback_payload = action.get('value') or action.get('payload')
    
    # 3. Проверяем attachments (inline_keyboard кнопки)
    if not callback_payload:
        attachments = body_data.get('attachments', [])
        for attachment in attachments:
            if attachment.get('type') == 'inline_keyboard':
                payload = attachment.get('payload', {})
                buttons = payload.get('buttons', [])
                for row in buttons:
                    for btn in row:
                        if btn.get('type') == 'callback' or 'action' in btn:
                            callback_payload = btn.get('payload') or btn.get('action', {}).get('value')
                            break
                    if callback_payload:
                        break
                if callback_payload:
                    break
    
    # Если это callback от кнопки
    if callback_payload:
        logger.info(f'Webhook: callback от пользователя {user_id}: {callback_payload}')
        # Передаём callback в executor
        from scenarios.services.executor import ScenarioExecutor
        from scenarios.models import Run, StepRun
        from accounts.models import User as AccountUser
        
        # Маппинг MAX user_id -> Django user_id
        django_user = AccountUser.objects.filter(max_id=str(user_id)).first()
        if not django_user:
            logger.warning(f'Webhook: пользователь с MAX user_id={user_id} не найден в Django')
            return JsonResponse({'status': 'ok'})
        
        # Ищем активный step_run для этого Django пользователя
        step_run = StepRun.objects.filter(
            recipient_id=django_user.pk,
            status=StepRun.STATUS_SENT,
        ).order_by('-step__step_order').first()
        
        if step_run:
            try:
                run = step_run.run
                executor = ScenarioExecutor(run)
                result = executor.process_answer(
                    user_id=django_user.pk,
                    message_text='',
                    button_result_code=callback_payload,
                )
                logger.info(f'Webhook: answer processed: {result}')
                
                # Если есть следующий шаг — отправляем сообщение с кнопками
                if result.get('success') and result.get('next_step_id'):
                    next_message = result.get('next_message', '')
                    if next_message:
                        try:
                            from scenarios.models import Step
                            next_step = Step.objects.filter(
                                pk=result['next_step_id'],
                                branch__scenario_id=result['scenario_id'],
                            ).first()
                            buttons = _extract_buttons_from_message_json(
                                next_step.message_json if next_step else None
                            )
                            client = MAXClient()
                            client.send_message(chat_id=chat_id, text=next_message, buttons=buttons)
                            logger.info(f'Webhook: next step sent to user {user_id}')
                        except MAXAPIError as e:
                            logger.error(f'Webhook: ошибка отправки следующего шага: {e}')
            except Exception as e:
                logger.error(f'Webhook: ошибка обработки callback: {e}')
        else:
            logger.warning(f'Webhook: нет активного step_run для пользователя {user_id}')
        
        return JsonResponse({'status': 'ok'})

    # Обработка текстовых сообщений
    if not message_text:
        return JsonResponse({'status': 'ok'})

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
