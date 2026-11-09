
@csrf_exempt
@require_POST
def max_webhook(request):
    """
    Webhook для приёма событий от MAX.
    
    MAX отправляет:
    - message_created — когда пользователь отправляет текстовое сообщение
    - message_callback — когда пользователь нажимает кнопку (ОБЯЗАТЕЛЬНО нужно ответить через /answers)
    """
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

    user_id = sender_data.get('user_id')
    chat_id = recipient_data.get('chat_id')
    message_text = body_data.get('text', '').strip()

    # ========================================================================
    # ОБРАБОТКА CALLBACK ОТ КНОПКИ (message_callback)
    # ========================================================================
    if update_type == 'message_callback':
        logger.info(f'Webhook CALLBACK: user_id={user_id}, chat_id={chat_id}, body={body_data}')
        
        # Извлекаем callback_id и result_code из обновления
        callback_id = data.get('callback_id') or body_data.get('callback_id')
        result_code = body_data.get('result_code')
        branch_code = body_data.get('branch_code')
        
        logger.info(f'Webhook CALLBACK: callback_id={callback_id}, result_code={result_code}, branch_code={branch_code}')
        
        if not user_id:
            logger.warning('Webhook CALLBACK: отсутствует user_id')
            return JsonResponse({'status': 'ok'})
        
        # Маппинг MAX user_id -> Django user_id
        from accounts.models import User as AccountUser
        django_user = AccountUser.objects.filter(max_id=str(user_id)).first()
        if not django_user:
            logger.warning(f'Webhook CALLBACK: пользователь с MAX user_id={user_id} не найден')
            return JsonResponse({'status': 'ok'})
        
        # Ищем активный step_run
        from scenarios.models import StepRun
        step_run = StepRun.objects.filter(
            recipient_id=django_user.pk,
            status=StepRun.STATUS_SENT,
        ).order_by('-step__step_order').first()
        
        if not step_run:
            logger.warning(f'Webhook CALLBACK: нет активного step_run для user {django_user.pk}')
            return JsonResponse({'status': 'ok'})
        
        # Отвечаем MAX через /answers (ОБЯЗАТЕЛЬНО по спецификации MAX API)
        from messaging.services.max_api import MAXClient as MAXClient2, MAXAPIError as MAXAPIError2
        try:
            client = MAXClient2()
            if callback_id:
                client.answer_callback(callback_id=callback_id)
                logger.info(f'Webhook CALLBACK: answered callback {callback_id}')
        except MAXAPIError2 as e:
            logger.error(f'Webhook CALLBACK: ошибка answer_callback: {e}')
        
        # Обрабатываем в сценарии
        from scenarios.services.executor import ScenarioExecutor
        from scenarios.models import Run
        
        run = step_run.run
        executor = ScenarioExecutor(run)
        
        # result_code из body_data — это код кнопки (WYG2X6GE и т.д.)
        button_result_code = result_code
        
        try:
            result = executor.process_answer(
                user_id=django_user.pk,
                message_text='',
                button_result_code=button_result_code,
            )
            logger.info(f'Webhook CALLBACK: answer processed: {result}')
            
            # Если есть следующий шаг — отправляем сообщение
            if result.get('success') and result.get('next_step_id'):
                next_message = result.get('next_message', '')
                if next_message:
                    try:
                        from messaging.services.bot_api_client import bot_api_client
                        from scenarios.models import Step
                        next_step = Step.objects.filter(
                            pk=result['next_step_id'],
                            branch__scenario_id=result['scenario_id'],
                        ).first()
                        buttons = _extract_buttons_from_message_json(
                            next_step.message_json if next_step else None
                        )
                        bot_api_client.send_message(
                            user_id=django_user.max_id,
                            text=next_message,
                            format='html',
                            buttons=buttons,
                        )
                        logger.info(f'Webhook CALLBACK: next step sent to user {django_user.pk}')
                    except Exception as e:
                        logger.error(f'Webhook CALLBACK: ошибка отправки следующего шага: {e}')
        except Exception as e:
            logger.error(f'Webhook CALLBACK: ошибка process_answer: {e}')
        
        return JsonResponse({'status': 'ok'})
    
    # ========================================================================
    # ОБРАБОТКА ТЕКСТОВОГО СООБЩЕНИЯ (message_created)
    # ========================================================================
    if update_type != 'message_created':
        logger.info(f'Webhook: игнорируем update_type={update_type}')
        return JsonResponse({'status': 'ok'})
    
    if not user_id:
        logger.warning('Webhook: отсутствует sender.user_id')
        return JsonResponse({'status': 'ok'})
    
    if sender_data.get('is_bot'):
        return JsonResponse({'status': 'ok'})
    
    logger.info(f'Webhook TEXT: user_id={user_id}, chat_id={chat_id}, text={message_text[:100]}')
    
    if not message_text:
        return JsonResponse({'status': 'ok'})
    
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
            from messaging.services.bot_api_client import bot_api_client
            bot_api_client.send_message(
                user_id=user_id,
                text=response_text,
                format='html',
            )
            logger.info(f'Webhook: ответ отправлен пользователю {user_id}')
        except Exception as e:
            logger.error(f'Webhook: ошибка отправки ответа: {e}')
    
    return JsonResponse({'status': 'ok'})
