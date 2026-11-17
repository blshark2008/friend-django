from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.core.cache import cache

from .models import Message, MessageRecipient, MailGroup
from .forms import MessageForm, MessageFilterForm
from accounts.models import User, Department


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


# ============================================================================
# Отправка сообщения конкретному пользователю
# ============================================================================

class SendMessageToUserView(LoginRequiredMixin, DetailView):
    """Отправка сообщения конкретному пользователю из модального окна."""
    model = User
    template_name = 'accounts/user_general.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()

        if not content:
            messages.warning(request, 'Введите текст сообщения.')
            return redirect('accounts:user_general', pk=user.pk)

        # Создаём сообщение
        message = Message.objects.create(
            sender=request.user,
            title=title,
            content=content,
            status=Message.STATUS_PENDING,
        )

        # Определяем каналы на основе настроек пользователя
        channels = []
        if user.notify_max and user.max_id:
            channels.append(Message.CHANNEL_MAX)
        if user.notify_telegram and user.telegram_id:
            channels.append(Message.CHANNEL_TELEGRAM)
        if user.notify_corporate_email and user.corporate_email:
            channels.append(Message.CHANNEL_EMAIL_CORPORATE)
        if user.notify_personal_email and user.personal_email:
            channels.append(Message.CHANNEL_EMAIL_PERSONAL)

        if not channels:
            messages.warning(
                request,
                f'У пользователя {user.get_full_name()} не настроены каналы связи. '
                'Сообщение сохранено как черновик.'
            )
            message.status = Message.STATUS_DRAFT
            message.save(update_fields=['status'])
            return redirect('accounts:user_general', pk=user.pk)

        # Создаём получателей по всем каналам
        for ch in channels:
            MessageRecipient.objects.get_or_create(
                message=message,
                recipient=user,
                delivery_channel=ch,
                defaults={'delivery_status': MessageRecipient.STATUS_PENDING},
            )

        # Отправляем
        from .services.dispatch import dispatch_message
        results = dispatch_message(message)
        messages.success(
            request,
            f'Сообщение отправлено пользователю {user.get_full_name()}. '
            f'Доставлено: {results["delivered"]}, Ошибок: {results["failed"]}'
        )
        return redirect('accounts:user_general', pk=user.pk)


# ============================================================================
# Поиск пользователей и подразделений (AJAX)
# ============================================================================

def search_users(request):
    """AJAX: поиск пользователей по ФИО и табельному номеру."""
    query = request.GET.get('q', '').strip()
    users = User.objects.filter(
        archive_status=User.STATUS_ACTIVE
    ).select_related('department', 'position')

    if query:
        users = users.filter(
            Q(last_name__icontains=query) |
            Q(first_name__icontains=query) |
            Q(patronymic__icontains=query) |
            Q(tab_number__icontains=query)
        )

    users = users.order_by('last_name', 'first_name')[:30]

    result = []
    for u in users:
        result.append({
            'id': u.pk,
            'name': u.get_full_name(),
            'tab_number': u.tab_number or '—',
            'department': u.department.name if u.department else '—',
            'position': u.position.name if u.position else '—',
        })

    return JsonResponse({'users': result})


def search_departments(request):
    """AJAX: поиск подразделений."""
    query = request.GET.get('q', '').strip()
    departments = Department.objects.filter(is_active=True)

    if query:
        departments = departments.filter(
            Q(name__icontains=query) |
            Q(code_1c__icontains=query)
        )

    departments = departments.order_by('name')[:30]

    result = []
    for d in departments:
        result.append({
            'id': d.pk,
            'name': d.name,
            'code': d.code_1c or '—',
            'parent': d.parent.name if d.parent else '—',
        })

    return JsonResponse({'departments': result})


def search_mail_groups(request):
    """AJAX: поиск групп рассылки."""
    query = request.GET.get('q', '').strip()
    groups = MailGroup.objects.all()

    if query:
        groups = groups.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    groups = groups.order_by('name')[:30]

    result = []
    for g in groups:
        result.append({
            'id': g.pk,
            'name': g.name,
            'description': g.description or 'Без описания',
            'member_count': g.member_count,
        })

    return JsonResponse({'groups': result})


# ============================================================================
# Список сообщений
# ============================================================================

class MessageListView(LoginRequiredMixin, ListView):
    """Список всех сообщений."""
    model = Message
    template_name = 'messaging/message_list.html'
    context_object_name = 'message_list'
    paginate_by = 20

    def get_queryset(self):
        qs = Message.objects.select_related('sender', 'department').prefetch_related('recipients')
        filter_form = MessageFilterForm(self.request.GET)

        if filter_form.is_valid():
            status = filter_form.cleaned_data.get('status')
            channel = filter_form.cleaned_data.get('channel')
            priority = filter_form.cleaned_data.get('priority')
            search = filter_form.cleaned_data.get('search', '').strip()

            if status:
                qs = qs.filter(status=status)
            if channel:
                qs = qs.filter(channel=channel)
            if priority:
                qs = qs.filter(priority=priority)
            if search:
                qs = qs.filter(
                    Q(title__icontains=search) | Q(content__icontains=search)
                )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = MessageFilterForm(self.request.GET)
        context['stats'] = {
            'total': Message.objects.count(),
            'draft': Message.objects.filter(status=Message.STATUS_DRAFT).count(),
            'sent': Message.objects.filter(status=Message.STATUS_SENT).count(),
            'failed': Message.objects.filter(status=Message.STATUS_FAILED).count(),
            'pending': Message.objects.filter(status=Message.STATUS_PENDING).count(),
        }
        return context


# ============================================================================
# Создание сообщения
# ============================================================================

class MessageCreateView(LoginRequiredMixin, CreateView):
    """Создание нового сообщения."""
    model = Message
    form_class = MessageForm
    template_name = 'messaging/message_form.html'

    def form_valid(self, form):
        form.instance.sender = self.request.user
        response = super().form_valid(form)

        # Парсим выбранных получателей, подразделения и группы рассылки из POST
        recipient_ids = [int(x) for x in self.request.POST.get('recipients', '').split(',') if x.strip()]
        department_ids = [int(x) for x in self.request.POST.get('departments', '').split(',') if x.strip()]
        group_ids = [int(x) for x in self.request.POST.get('mail_groups', '').split(',') if x.strip()]

        if not recipient_ids and not department_ids and not group_ids:
            messages.error(self.request, 'Укажите получателей или подразделения для рассылки.')
            return self.form_invalid(form)

        # Собираем всех получателей (индивидуальные + из подразделений + из групп рассылки)
        recipients = User.objects.filter(pk__in=recipient_ids) if recipient_ids else []
        departments = Department.objects.filter(pk__in=department_ids) if department_ids else []
        mail_groups = MailGroup.objects.filter(pk__in=group_ids) if group_ids else []

        # Используем dict для дедупликации по user_id
        all_users = {}

        # Индивидуальные получатели
        for user in recipients:
            all_users[user.pk] = user

        # Получатели из подразделений
        if departments:
            dept_users = User.objects.filter(
                department__in=departments,
                archive_status=User.STATUS_ACTIVE
            )
            for user in dept_users:
                all_users[user.pk] = user

        # Получатели из групп рассылки
        if mail_groups:
            for group in mail_groups:
                group_users = group.users.filter(archive_status=User.STATUS_ACTIVE)
                for user in group_users:
                    all_users[user.pk] = user

        # Создаём получателей сообщений
        for user in all_users.values():
            self._create_recipients_all_channels(user)

        messages.success(self.request, 'Сообщение создано и отправлено в обработку.')
        return redirect('messaging:message_detail', pk=self.object.pk)

    def _create_recipients_all_channels(self, user):
        """Создаём записи о доставке для пользователя по всем активным каналам."""
        channels_to_use = []
        if user.notify_max and user.max_id:
            channels_to_use.append(Message.CHANNEL_MAX)
        if user.notify_telegram and user.telegram_id:
            channels_to_use.append(Message.CHANNEL_TELEGRAM)
        if user.notify_corporate_email and user.corporate_email:
            channels_to_use.append(Message.CHANNEL_EMAIL_CORPORATE)
        if user.notify_personal_email and user.personal_email:
            channels_to_use.append(Message.CHANNEL_EMAIL_PERSONAL)

        for ch in channels_to_use:
            MessageRecipient.objects.get_or_create(
                message=self.object,
                recipient=user,
                delivery_channel=ch,
                defaults={
                    'delivery_status': MessageRecipient.STATUS_PENDING,
                }
            )


# ============================================================================
# Детали сообщения
# ============================================================================

class MessageDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о сообщении."""
    model = Message
    template_name = 'messaging/message_detail.html'
    context_object_name = 'message'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recipients'] = self.object.recipients.all().select_related('recipient')
        context['total_recipients'] = self.object.recipient_count
        context['delivered_count'] = self.object.delivered_count
        return context


# ============================================================================
# Редактирование сообщения
# ============================================================================

class MessageUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование сообщения (только черновиков)."""
    model = Message
    form_class = MessageForm
    template_name = 'messaging/message_form.html'

    def get_queryset(self):
        return Message.objects.filter(status=Message.STATUS_DRAFT)

    def form_valid(self, form):
        form.instance.sender = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, 'Сообщение обновлено.')
        return reverse_lazy('messaging:message_detail', kwargs={'pk': self.object.pk})


# ============================================================================
# Удаление сообщения
# ============================================================================

class MessageDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление сообщения."""
    model = Message
    template_name = 'messaging/message_confirm_delete.html'
    success_url = reverse_lazy('messaging:message_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Сообщение удалено.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# Отправка сообщения
# ============================================================================

def send_message(request, pk):
    """Запуск отправки сообщения."""
    message = get_object_or_404(Message, pk=pk)
    if request.method == 'POST':
        message.status = Message.STATUS_PENDING
        message.save(update_fields=['status'])

        # Запускаем отправку
        from .services.dispatch import dispatch_message
        results = dispatch_message(message)
        messages.success(
            request,
            f'Отправка запущена. Доставлено: {results["delivered"]}, Ошибок: {results["failed"]}'
        )
        return redirect('messaging:message_detail', pk=pk)
    return redirect('messaging:message_detail', pk=pk)


# ============================================================================
# Статистика
# ============================================================================

class MessageStatsView(LoginRequiredMixin, DetailView):
    """Статистика по сообщениям."""
    model = Message
    template_name = 'messaging/message_stats.html'
    context_object_name = 'message'

    def get_object(self, queryset=None):
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total'] = Message.objects.count()
        context['by_status'] = dict(
            Message.objects.values_list('status').annotate(count=Count('id'))
        )
        context['by_channel'] = dict(
            Message.objects.values_list('channel').annotate(count=Count('id'))
        )
        context['recent_messages'] = Message.objects.select_related('sender').all()[:20]
        return context


# ============================================================================
# MAX Bot Webhook — надёжный handler с хранением chat_id в БД
# ============================================================================

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from messaging.bots.max_bot import handle_command, handle_message, session_store, BotState
from messaging.services.max_api import MAXClient, MAXAPIError
from messaging.services.bot_api_client import bot_api_client

logger = logging.getLogger(__name__)


def _get_django_user(user_id):
    """Найти Django-пользователя по MAX user_id."""
    from accounts.models import User as AccountUser
    return AccountUser.objects.filter(max_id=str(user_id)).first()


def _get_user_chat_id(user_id, django_user=None):
    """
    Получить chat_id пользователя.
    
    Приоритет:
    1. chat_id из БД (user.max_chat_id) — сохраняется между перезапусками
    2. chat_id из session_store (in-memory fallback) — для быстрых ответов
    3. None — если не найден нигде
    
    Args:
        user_id: MAX user_id (int/str)
        django_user: уже загруженный Django User (опционально)
    
    Returns:
        int/None: chat_id или None
    """
    # Сначала пробуем из БД
    if django_user and django_user.max_chat_id:
        return django_user.max_chat_id
    
    # Если пользователь не загружен — загружаем
    if not django_user:
        django_user = _get_django_user(user_id)
    
    if django_user and django_user.max_chat_id:
        return django_user.max_chat_id
    
    # Fallback: из session store (in-memory)
    session = session_store.get(user_id) or {}
    return session.get('chat_id')


def _save_user_chat_id(django_user, chat_id):
    """
    Сохранить chat_id пользователя в БД.
    
    Вызывается при bot_started и при получении любого события от пользователя.
    """
    if chat_id and django_user:
        try:
            # Обновляем только это поле (efficient)
            User = type(django_user)
            User.objects.filter(pk=django_user.pk).update(max_chat_id=chat_id)
            django_user.max_chat_id = chat_id
            logger.info(f'Saved chat_id={chat_id} for user max_id={django_user.max_id} (pk={django_user.pk})')
        except Exception as e:
            logger.error(f'Error saving chat_id for user {django_user.max_id}: {e}')


def _find_active_steprun(django_user):
    """Найти активный StepRun для пользователя по текущему запуску."""
    from scenarios.models import StepRun, UserCurrentRun
    current_run = UserCurrentRun.objects.filter(user=django_user).first()
    if not current_run or not current_run.run:
        logger.info(f'_find_active_steprun: no current run for user {django_user.pk}')
        return None
    
    logger.info(f'_find_active_steprun: current run_id={current_run.run.id}')
    return StepRun.objects.filter(
        recipient_id=django_user.pk,
        status=StepRun.STATUS_SENT,
        run=current_run.run,
    ).order_by('-step__step_order').first()


def _find_active_steprun_for_button(django_user, button_code):
    """Найти активный StepRun, содержащий кнопку с данным result_code."""
    from scenarios.models import StepRun, UserCurrentRun
    current_run = UserCurrentRun.objects.filter(user=django_user).first()
    if not current_run or not current_run.run:
        logger.info(f'_find_active_steprun_for_button: no current run for user {django_user.pk}')
        return None
    
    step_runs = StepRun.objects.filter(
        recipient_id=django_user.pk,
        status=StepRun.STATUS_SENT,
        run=current_run.run,
    ).order_by('-step__step_order')
    
    for sr in step_runs:
        message_json = sr.step.message_json
        if isinstance(message_json, dict):
            options = message_json.get('options', [])
            for opt in options:
                if opt.get('result_code') == button_code:
                    logger.info(f'_find_active_steprun_for_button: found step_run_id={sr.pk}, step_id={sr.step.id}, button_code={button_code}')
                    return sr
    logger.info(f'_find_active_steprun_for_button: no matching step_run for button_code={button_code}')
    return None


def _find_active_steprun_for_text(django_user):
    """Найти активный StepRun, содержащий number/text_pattern тип."""
    from scenarios.models import StepRun, UserCurrentRun
    current_run = UserCurrentRun.objects.filter(user=django_user).first()
    if not current_run or not current_run.run:
        logger.info(f'_find_active_steprun_for_text: no current run for user {django_user.pk}')
        return None
    
    step_runs = StepRun.objects.filter(
        recipient_id=django_user.pk,
        status=StepRun.STATUS_SENT,
        run=current_run.run,
    ).order_by('-step__step_order')
    
    for sr in step_runs:
        message_json = sr.step.message_json
        if isinstance(message_json, dict):
            msg_type = message_json.get('type', '')
            if msg_type in ('number', 'text_pattern'):
                logger.info(f'_find_active_steprun_for_text: found step_run_id={sr.pk}, step_id={sr.step.id}, type={msg_type}')
                return sr
    logger.info(f'_find_active_steprun_for_text: no matching step_run found')
    return None


def _send_message_to_user(user_id, django_user, text, buttons=None, format='html'):
    """
    Отправить сообщение пользователю с fallback логикой.
    
    Приоритет:
    1. chat_id из БД (надёжно, сохраняется между перезапусками)
    2. user_id (работает в диалоге с ботом)
    """
    chat_id = _get_user_chat_id(user_id, django_user)
    
    # Если пользователь не найден в БД, отправляем только по user_id
    if not django_user:
        try:
            bot_api_client.send_message(
                user_id=user_id,
                chat_id=chat_id,
                text=text,
                format=format,
                buttons=buttons,
            )
            logger.info(f'Message sent to unregistered user {user_id} (chat_id={chat_id})')
        except Exception as e:
            logger.error(f'Failed to send to unregistered user {user_id}: {e}')
        return
    
    try:
        bot_api_client.send_message(
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            format=format,
            buttons=buttons,
        )
        logger.info(f'Message sent to user {user_id} (chat_id={chat_id}, max_id={django_user.max_id})')
    except Exception as e:
        # Fallback: пробуем отправить только по user_id
        if chat_id:
            logger.warning(f'Failed to send with chat_id={chat_id}, retrying with user_id only: {e}')
            try:
                bot_api_client.send_message(
                    user_id=user_id,
                    chat_id=None,
                    text=text,
                    format=format,
                    buttons=buttons,
                )
                logger.info(f'Message sent via fallback (user_id only) to {user_id}')
            except Exception as e2:
                logger.error(f'Fallback send also failed for user {user_id}: {e2}')
        else:
            logger.error(f'Failed to send message to user {user_id}: {e}')


def _process_button_result(django_user, result_code, callback_id=None, chat_id=None):
    """Обработать результат нажатия кнопки и отправить следующий шаг."""
    from scenarios.services.executor import ScenarioExecutor

    # Ищем StepRun, содержащий кнопку с данным result_code
    step_run = _find_active_steprun_for_button(django_user, result_code)
    if not step_run:
        logger.info(f'No matching StepRun for result_code={result_code}, user_id={django_user.pk}')
        return

    logger.info(f'_process_button_result: user_id={django_user.pk}, result_code={result_code}, step_run_id={step_run.pk}, step_id={step_run.step.id}')

    # Обрабатываем ответ в сценарии
    # executor.process_answer() сам отправляет следующий шаг через _send_next_step()
    run = step_run.run
    executor = ScenarioExecutor(run)
    try:
        result = executor.process_answer(
            user_id=django_user.pk,
            message_text='',
            button_result_code=result_code,
            step_run=step_run,
        )
        logger.info(f'Button processed: {result}')

        # Ответ на callback только после успешной валидации
        # MAX API позволяет ответить на callback в течение ~40 секунд
        if result.get('success') and callback_id:
            try:
                client = MAXClient()
                client.answer_callback_simple(callback_id=callback_id)
                logger.info(f'Answered callback: {callback_id}')
            except MAXAPIError as e:
                logger.error(f'answer_callback error (callback expired): {e}')
    except Exception as e:
        logger.error(f'process_answer error: {e}')


@csrf_exempt
@require_POST
def max_webhook(request):
    '''Webhook для приёма событий от MAX.

    Структура событий согласно документации MAX API:
    - message_callback: {update_type, callback: {callback_id, payload, user: {user_id}, message}}
    - message_created:  {update_type, message: {sender: {user_id, is_bot}, body: {text}}}
    - bot_started:      {update_type, chat_id, user: {user_id}, payload}
    '''
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f'JSON decode error: {e}')
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    update_type = data.get('update_type', '')
    logger.info(f'Webhook received: update_type={update_type}, data keys={list(data.keys())}')

    # ========================================================================
    # ОБРАБОТКА CALLBACK ОТ КНОПКИ (message_callback)
    # ========================================================================
    if update_type == 'message_callback':
        callback_data = data.get('callback', {})
        callback_id = callback_data.get('callback_id')
        payload = callback_data.get('payload', '')
        user_data = callback_data.get('user', {})
        user_id = user_data.get('user_id')

        logger.info(f'message_callback: callback_id={callback_id}, payload={payload}, user_id={user_id}')

        if not user_id:
            return JsonResponse({'status': 'ok'})

        # Защита от дублирования callback-событий (MAX может отправить одно событие дважды)
        # Защита 1: по callback_id (если MAX отправляет один callback_id дважды)
        if callback_id:
            cache_key = f'callback_id:{callback_id}'
            if cache.get(cache_key):
                logger.info(f'Duplicate callback (by ID) ignored: {callback_id}')
                try:
                    from messaging.services.max_api import MAXClient
                    client = MAXClient()
                    client.answer_callback_simple(callback_id=callback_id)
                except Exception:
                    pass
                return JsonResponse({'status': 'ok'})
            cache.set(cache_key, '1', timeout=60)

        # Защита 2: по user_id + payload (если MAX отправляет разные callback_id с одинаковым payload)
        dedup_key = f'payload:{user_id}:{payload}'
        if cache.get(dedup_key):
            logger.info(f'Duplicate callback (by payload) ignored: user={user_id}, payload={payload}')
            # Отвечаем на callback, чтобы MAX убрал индикатор загрузки
            if callback_id:
                try:
                    from messaging.services.max_api import MAXClient
                    client = MAXClient()
                    client.answer_callback_simple(callback_id=callback_id)
                except Exception:
                    pass
            return JsonResponse({'status': 'ok'})
        cache.set(dedup_key, '1', timeout=30)  # 30 секунд на обработку

        django_user = _get_django_user(user_id)
        if not django_user:
            logger.warning(f'User {user_id} not found in Django')
            return JsonResponse({'status': 'ok'})

        # Получаем chat_id из БД или сессии
        chat_id = _get_user_chat_id(user_id, django_user)
        _process_button_result(django_user, result_code=payload, callback_id=callback_id, chat_id=chat_id)
        return JsonResponse({'status': 'ok'})

    # ========================================================================
    # ОБРАБОТКА СООБЩЕНИЯ (message_created)
    # ========================================================================
    if update_type == 'message_created':
        message_data = data.get('message', {})
        sender_data = message_data.get('sender', {})
        body_data = message_data.get('body', {})

        user_id = sender_data.get('user_id')
        is_bot = sender_data.get('is_bot', False)
        message_text = body_data.get('text', '').strip()

        logger.info(f'message_created: user_id={user_id}, is_bot={is_bot}, text={message_text[:100]}')

        if not user_id or is_bot:
            return JsonResponse({'status': 'ok'})
        if not message_text:
            return JsonResponse({'status': 'ok'})

        # Проверяем, ожидает ли пользователь ответ на кнопку
        django_user = _get_django_user(user_id)
        if django_user:
            # Сохраняем chat_id в БД при первом сообщении
            chat_id = _get_user_chat_id(user_id, django_user)
            if not chat_id:
                # Пробуем получить из message_data
                recipient_data = message_data.get('recipient', {})
                chat_id = recipient_data.get('chat_id')
                if chat_id:
                    _save_user_chat_id(django_user, chat_id)
            
            # Сначала проверяем, совпадает ли текст с любой кнопкой среди активных step_run'ов
            from scenarios.models import StepRun, UserCurrentRun
            current_run = UserCurrentRun.objects.filter(user=django_user).first()
            if not current_run or not current_run.run:
                logger.info(f'message_created: no current run for user {django_user.pk}')
                return JsonResponse({'status': 'ok'})
            
            logger.info(f'message_created: current run_id={current_run.run.id}')
            step_runs = StepRun.objects.filter(
                recipient_id=django_user.pk,
                status=StepRun.STATUS_SENT,
                run=current_run.run,
            ).order_by('-step__step_order')
            
            logger.info(f'message_created: checking {step_runs.count()} step_runs for button match')
            
            # Собираем все step_run'ы с кнопками
            button_step_runs = []
            for sr in step_runs:
                message_json = sr.step.message_json
                if isinstance(message_json, dict):
                    msg_type = message_json.get('type', '')
                    logger.info(f'message_created: step_run_id={sr.pk}, step_id={sr.step.id}, step_order={sr.step.step_order}, msg_type={msg_type}')
                    if msg_type in ('buttons', 'buttons_with_number'):
                        button_step_runs.append(sr)
            
            # Проверяем совпадение текста с кнопкой (начиная с последнего step_run)
            for sr in button_step_runs:
                options = sr.step.message_json.get('options', [])
                for opt in options:
                    btn_text = opt.get('text', '').strip()
                    if btn_text and (
                        btn_text.lower() == message_text.lower() or
                        message_text.lower().startswith(btn_text.lower()) or
                        btn_text.lower().startswith(message_text.lower())
                    ):
                        result_code = opt.get('result_code', '')
                        logger.info(f'Matched button text "{message_text}" -> rc={result_code} (step_run_id={sr.pk})')
                        _process_button_result(django_user, result_code=result_code, chat_id=chat_id)
                        return JsonResponse({'status': 'ok'})
            
            # Затем ищем StepRun с number/text_pattern (текстовый ответ)
            step_run = _find_active_steprun_for_text(django_user)
            if step_run:
                logger.info(f'message_created: found text step_run_id={step_run.pk}, step_id={step_run.step.id}')
                step = step_run.step
                message_json = step.message_json
                msg_type = message_json.get('type', '')
                
                from scenarios.services.executor import ScenarioExecutor
                run = step_run.run
                executor = ScenarioExecutor(run)
                result = executor.process_answer(django_user.pk, message_text, step_run=step_run)
                logger.info(f'Text answer processed: {result}')
                return JsonResponse({'status': 'ok'})

        # Обычный текст — команды и сообщения
        response_text = None
        if message_text.startswith('/'):
            parts = message_text.split(' ', 1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ''
            response_text = handle_command(user_id, command, args)
        else:
            response_text = handle_message(user_id, message_text)

        if response_text:
            _send_message_to_user(
                user_id=user_id,
                django_user=django_user,
                text=response_text,
            )
        return JsonResponse({'status': 'ok'})

    # ========================================================================
    # ОБРАБОТКА ЗАПУСКА БОТА (bot_started)
    # ========================================================================
    if update_type == 'bot_started':
        user_data = data.get('user', {})
        user_id = user_data.get('user_id')
        chat_id = data.get('chat_id')
        payload = data.get('payload')
        logger.info(f'bot_started: user_id={user_id}, chat_id={chat_id}, payload={payload}')

        if user_id:
            # Находим пользователя
            django_user = _get_django_user(user_id)
            
            # Сохраняем chat_id в БД для отправки ответов
            if django_user:
                _save_user_chat_id(django_user, chat_id)
            else:
                # Если пользователь не найден, сохраняем в сессию как fallback
                session = session_store.get(user_id) or {}
                session['chat_id'] = chat_id
                session_store.set(user_id, session)

            response = handle_command(user_id, 'start', payload or '')
            if response:
                _send_message_to_user(
                    user_id=user_id,
                    django_user=django_user,
                    text=str(response),
                )
        return JsonResponse({'status': 'ok'})

    # ========================================================================
    # ОБРАБОТКА ДОБАВЛЕНИЯ БОТА (bot_added)
    # ========================================================================
    if update_type == 'bot_added':
        user_data = data.get('user', {})
        chat_id = data.get('chat_id')
        logger.info(f'bot_added: chat_id={chat_id}, user={user_data}')
        return JsonResponse({'status': 'ok'})

    # Неизвестный тип — игнорируем
    logger.info(f'Unknown update_type: {update_type}')
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_POST
def api_max_webhook(request):
    '''API webhook - алиас.'''
    return max_webhook(request)
