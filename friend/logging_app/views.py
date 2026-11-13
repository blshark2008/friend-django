from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import ListView
from django.db import models
from django.utils import timezone
from django.shortcuts import render

from .models import LogEntry


# ============================================================================
# Веб-интерфейс журнала
# ============================================================================

class LogListView(LoginRequiredMixin, ListView):
    """Список записей журнала."""
    model = LogEntry
    template_name = 'logging_app/log_list.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        qs = LogEntry.objects.select_related().all()
        q = self.request.GET.get('q', '').strip()
        source_filter = self.request.GET.get('source', '').strip()
        action_filter = self.request.GET.get('action', '').strip()
        severity_filter = self.request.GET.get('severity', '').strip()
        actor_filter = self.request.GET.get('actor', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()

        if source_filter:
            qs = qs.filter(source=source_filter)
        if action_filter:
            qs = qs.filter(action=action_filter)
        if severity_filter:
            qs = qs.filter(severity=severity_filter)
        if actor_filter:
            qs = qs.filter(actor__icontains=actor_filter)
        if date_from:
            qs = qs.filter(timestamp__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__lte=date_to + ' 23:59:59')

        if q:
            qs = qs.filter(
                models.Q(actor__icontains=q)
                | models.Q(summary__icontains=q)
                | models.Q(target_display__icontains=q)
                | models.Q(source__icontains=q),
            ).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sources'] = LogEntry.objects.values_list('source', flat=True).distinct()
        context['actions'] = LogEntry.Action.choices
        context['severities'] = LogEntry.Severity.choices
        context['current_source'] = self.request.GET.get('source', '')
        context['current_action'] = self.request.GET.get('action', '')
        context['current_severity'] = self.request.GET.get('severity', '')
        context['current_actor'] = self.request.GET.get('actor', '')
        context['current_date_from'] = self.request.GET.get('date_from', '')
        context['current_date_to'] = self.request.GET.get('date_to', '')
        context['current_q'] = self.request.GET.get('q', '')
        context['logs_count'] = LogEntry.objects.count()
        context['today_count'] = LogEntry.objects.filter(
            timestamp__date=timezone.now().date()
        ).count()
        context['warning_count'] = LogEntry.objects.filter(
            severity__in=[LogEntry.Severity.WARNING, LogEntry.Severity.ERROR, LogEntry.Severity.CRITICAL]
        ).count()
        return context


# ============================================================================
# API для приёма событий от других приложений
# ============================================================================

def api_log_event(request):
    """API endpoint для приёма событий от других приложений.

    POST /api/logging/event/
    Body (JSON):
    {
        "source": "access",
        "action": "update",
        "severity": "info",
        "actor": "admin",
        "actor_type": "user",
        "target_model": "AccessGroup",
        "target_id": 5,
        "target_display": "fs-share-prod-rw",
        "summary": "Группа обновлена",
        "details": {"changed_fields": ["name", "description"]},
        "ip_address": "127.0.0.1"
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    try:
        import json
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Required fields
    source = data.get('source', 'custom')
    action = data.get('action', 'custom')
    summary = data.get('summary', '')
    target_display = data.get('target_display', '')

    if not source or not action:
        return JsonResponse({'error': 'source and action are required'}, status=400)

    # Validate action
    valid_actions = [a[0] for a in LogEntry.Action.choices]
    if action not in valid_actions:
        return JsonResponse({'error': f'Invalid action. Valid: {valid_actions}'}, status=400)

    # Validate severity
    severity = data.get('severity', 'info')
    valid_severities = [s[0] for s in LogEntry.Severity.choices]
    if severity not in valid_severities:
        severity = 'info'

    # Create log entry
    entry = LogEntry.objects.create(
        source=source,
        action=action,
        severity=severity,
        actor=data.get('actor', 'system'),
        actor_type=data.get('actor_type', 'system'),
        target_model=data.get('target_model', ''),
        target_id=data.get('target_id'),
        target_display=target_display,
        summary=summary,
        details=data.get('details', {}),
        ip_address=data.get('ip_address', request.META.get('REMOTE_ADDR')),
        user_agent=data.get('user_agent', ''),
    )

    return JsonResponse({
        'status': 'ok',
        'id': entry.pk,
        'timestamp': entry.timestamp.isoformat(),
    }, status=201)
