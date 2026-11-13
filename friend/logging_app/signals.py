from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model

from access.models import AccessGroup, AccessGrant, Resource
from .models import LogEntry

User = get_user_model()


def get_current_user_from_request():
    """Получает текущего пользователя из контекста запроса."""
    try:
        from django.http import HttpRequest
        # This is a workaround - in signals we don't have direct access to request
        # The actor is passed via thread-local or we use system as default
        return None
    except ImportError:
        return None


def get_client_ip(request):
    """Получает IP-адрес клиента из запроса."""
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    return ''


def log_access_group_change(instance, action, summary, details=None, request=None):
    """Записывает событие изменения группы доступа в журнал."""
    LogEntry.objects.create(
        source='access',
        action=action,
        severity='info',
        actor=request.user.get_full_name() if request and hasattr(request, 'user') and request.user.is_authenticated else 'system',
        actor_type='user' if request and hasattr(request, 'user') and request.user.is_authenticated else 'system',
        target_model='AccessGroup',
        target_id=instance.pk,
        target_display=instance.display_name if hasattr(instance, 'display_name') else str(instance),
        summary=summary,
        details=details or {},
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


@receiver(post_save, sender=AccessGroup)
def log_access_group_save(sender, instance, created, update_fields, **kwargs):
    """Логирование создания/обновления группы доступа."""
    if created:
        log_access_group_change(
            instance,
            LogEntry.Action.CREATE,
            f'Группа создана: {instance.display_name}',
            {'fields': {
                'type_prefix': instance.type_prefix,
                'resource_name': instance.resource_name,
                'area': instance.area,
                'access_level': instance.access_level,
                'is_active': instance.is_active,
            }},
        )
    elif update_fields:
        # Determine what changed
        try:
            old_instance = AccessGroup.objects.get(pk=instance.pk)
            changed = {}
            for field in update_fields:
                old_val = getattr(old_instance, field, None)
                new_val = getattr(instance, field, None)
                if old_val != new_val:
                    changed[field] = {'old': str(old_val), 'new': str(new_val)}
            if changed:
                log_access_group_change(
                    instance,
                    LogEntry.Action.UPDATE,
                    f'Группа обновлена: {instance.display_name}',
                    {'changed_fields': changed},
                )
        except AccessGroup.DoesNotExist:
            pass


@receiver(post_save, sender=AccessGroup)
def log_access_group_archive(sender, instance, created, **kwargs):
    """Логирование архивирования группы."""
    if not created and not instance.is_active:
        log_access_group_change(
            instance,
            LogEntry.Action.ARCHIVE,
            f'Группа архивирована: {instance.display_name}',
            {'old_status': 'active', 'new_status': 'archived'},
        )


@receiver(post_save, sender=AccessGroup)
def log_access_group_restore(sender, instance, created, **kwargs):
    """Логирование восстановления группы."""
    if not created and instance.is_active:
        try:
            # Check if it was previously archived
            history = LogEntry.objects.filter(
                source='access',
                target_model='AccessGroup',
                target_id=instance.pk,
                action=LogEntry.Action.ARCHIVE,
            ).order_by('-timestamp').first()
            if history:
                log_access_group_change(
                    instance,
                    LogEntry.Action.RESTORE,
                    f'Группа восстановлена: {instance.display_name}',
                    {'restored_from': 'archive'},
                )
        except Exception:
            pass


@receiver(pre_delete, sender=AccessGroup)
def log_access_group_delete(sender, instance, **kwargs):
    """Логирование удаления группы (soft delete handled in view)."""
    log_access_group_change(
        instance,
        LogEntry.Action.DELETE,
        f'Группа удалена: {instance.display_name}',
        {'fields': {
            'type_prefix': instance.type_prefix,
            'resource_name': instance.resource_name,
            'area': instance.area,
            'access_level': instance.access_level,
        }},
    )


# ============================================================================
# Логирование AccessGrant
# ============================================================================

@receiver(post_save, sender=AccessGrant)
def log_access_grant_save(sender, instance, created, **kwargs):
    """Логирование создания/обновления гранта доступа."""
    if created:
        log_access_group_change(
            instance,
            LogEntry.Action.GRANT,
            f'Доступ предоставлен: {instance.user.get_full_name() if instance.user else instance.group.name} → {instance.resource.name}',
            {
                'resource': instance.resource.name,
                'level': instance.level,
                'expires_at': str(instance.expires_at) if instance.expires_at else None,
            },
        )


# ============================================================================
# Логирование Resource
# ============================================================================

@receiver(post_save, sender=Resource)
def log_resource_save(sender, instance, created, **kwargs):
    """Логирование создания/обновления ресурса."""
    if created:
        LogEntry.objects.create(
            source='access',
            action=LogEntry.Action.CREATE,
            severity='info',
            actor='system',
            actor_type='system',
            target_model='Resource',
            target_id=instance.pk,
            target_display=instance.name,
            summary=f'Ресурс создан: {instance.name} ({instance.get_type_display()})',
            details={'type': instance.type, 'is_active': instance.is_active},
        )
