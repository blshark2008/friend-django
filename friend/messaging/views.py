from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q, Count
from django.http import JsonResponse

from .models import Message, MessageRecipient
from .forms import MessageForm, MessageFilterForm
from accounts.models import User, Department


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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.sender = self.request.user
        response = super().form_valid(form)

        # Создаём получателей
        recipients = form.cleaned_data.get('recipients', [])
        department = form.cleaned_data.get('department')
        channel = form.instance.channel

        if recipients:
            for recipient in recipients:
                # Проверяем, разрешены ли каналы для этого пользователя
                self._create_recipients(recipient, channel)

        if department:
            # Рассылка по подразделению — только пользователи с включёнными каналами
            dept_users = User.objects.filter(
                department=department,
                archive_status=User.STATUS_ACTIVE
            )
            for user in dept_users:
                self._create_recipients(user, channel)

        messages.success(self.request, 'Сообщение создано и отправлено в обработку.')
        return redirect('messaging:message_detail', pk=self.object.pk)

    def _create_recipients(self, user, channel):
        """Создаём записи о доставке для пользователя по указанному каналу."""
        # Определяем реальные каналы на основе настроек пользователя
        channels_to_use = []
        if channel == Message.CHANNEL_MAX and user.notify_max and user.max_id:
            channels_to_use.append(Message.CHANNEL_MAX)
        elif channel == Message.CHANNEL_TELEGRAM and user.notify_telegram and user.telegram_id:
            channels_to_use.append(Message.CHANNEL_TELEGRAM)
        elif channel == Message.CHANNEL_EMAIL_CORPORATE and user.notify_corporate_email and user.corporate_email:
            channels_to_use.append(Message.CHANNEL_EMAIL_CORPORATE)
        elif channel == Message.CHANNEL_EMAIL_PERSONAL and user.notify_personal_email and user.personal_email:
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
def max_webhook(request):
    """
    Webhook для приёма сообщений от MAX.
    
    Ожидаемый формат входящего JSON:
    {
        "type": "message",
        "user": {"id": "user_max_id", "username": "username"},
        "message": {"text": "/register", "id": "msg_id"},
        "timestamp": 1234567890
    }
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f'JSON decode error: {e}')
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    user_data = data.get('user', {})
    message_data = data.get('message', {})
    user_id = user_data.get('id', '')
    message_text = message_data.get('text', '').strip()

    if not user_id:
        logger.warning('Webhook: отсутствует user.id')
        return JsonResponse({'status': 'error', 'message': 'Missing user.id'}, status=400)

    if not message_text:
        return JsonResponse({'status': 'ok'})

    logger.info(f'Webhook: user_id={user_id}, text={message_text[:100]}')

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
            client.send_message(user_id, response_text)
            logger.info(f'Webhook: ответ отправлен пользователю {user_id}')
        except MAXAPIError as e:
            logger.error(f'Webhook: ошибка отправки ответа: {e}')
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to send response',
                'error': str(e),
            }, status=500)

    return JsonResponse({'status': 'ok'})
