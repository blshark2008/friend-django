from django.contrib import admin
from .models import LogEntry


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'severity_badge', 'source', 'action', 'actor', 'target_display', 'ip_address')
    list_filter = ('severity', 'action', 'source', 'actor_type', 'timestamp')
    search_fields = ('actor', 'summary', 'target_display', 'ip_address')
    readonly_fields = ('timestamp', 'severity_badge')
    date_hierarchy = 'timestamp'
    list_per_page = 50

    def severity_badge(self, obj):
        css = {
            'info': 'background: #0d6efd; color: white; padding: 2px 8px; border-radius: 4px;',
            'warning': 'background: #ffc107; color: black; padding: 2px 8px; border-radius: 4px;',
            'error': 'background: #dc3545; color: white; padding: 2px 8px; border-radius: 4px;',
            'critical': 'background: #6f0000; color: white; padding: 2px 8px; border-radius: 4px;',
        }
        return format_html(
            '<span style="{}">{}</span>',
            css.get(obj.severity, ''),
            obj.get_severity_display(),
        )
    severity_badge.short_description = 'Серьёзность'
