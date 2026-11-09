from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

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
    context_object_name = 'messages'
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
# MAX Bot Webhook
# ============================================================================

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from messaging.bots.max_bot import handle_command, handle_message
from messaging.services.max_api import MAXClient, MAXAPIError

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST

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
                client.answer_callback_simple(callback_id=callback_id)
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
