from django.contrib import admin
from .models import (
    Host, InventorySnapshot, SecurityEvent,
    RecentLogin, EmployeeLeave, LeaveType, AbsenceAlert,
)


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'os_info', 'os_type', 'ip_address', 'serial_number',
                    'antivirus_installed', 'last_seen', 'is_active', 'offline_badge')
    list_filter = ('is_active', 'antivirus_installed', 'os_type')
    search_fields = ('hostname', 'serial_number', 'os_info', 'ip_address', 'mac_address')
    readonly_fields = ('created_at', 'updated_at', 'last_seen')

    def offline_badge(self, obj):
        if obj.is_offline:
            return '<span class="badge bg-danger">Оффлайн</span>'
        return '<span class="badge bg-success">Онлайн</span>'
    offline_badge.short_description = 'Статус'
    offline_badge.allow_tags = True


@admin.register(InventorySnapshot)
class InventorySnapshotAdmin(admin.ModelAdmin):
    list_display = ('host', 'collected_at', 'cpu_model', 'cpu_temperature',
                    'ram_mb', 'packages_count', 'pending_updates_count',
                    'open_ports_count')
    list_filter = ('collected_at',)
    search_fields = ('host__hostname',)
    readonly_fields = ('collected_at',)

    def pending_updates_count(self, obj):
        if obj.pending_updates:
            return len(obj.pending_updates)
        return 0
    pending_updates_count.short_description = 'Обновления'

    def open_ports_count(self, obj):
        return len(obj.open_ports)
    open_ports_count.short_description = 'Порты'


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ('host', 'event_type', 'severity', 'message_short',
                    'occurred_at', 'created_at')
    list_filter = ('event_type', 'severity', 'occurred_at')
    search_fields = ('host__hostname', 'message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'occurred_at'

    def message_short(self, obj):
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message
    message_short.short_description = 'Сообщение'


@admin.register(RecentLogin)
class RecentLoginAdmin(admin.ModelAdmin):
    list_display = ('username', 'host', 'login_time', 'matched_user_display', 'is_matched')
    list_filter = ('is_matched',)
    search_fields = ('username', 'host__hostname', 'matched_user__username',
                     'matched_user__last_name', 'matched_user__first_name')
    date_hierarchy = 'login_time'
    readonly_fields = ('host', 'username', 'source', 'login_time',
                       'matched_user', 'is_matched', 'created_at')

    def matched_user_display(self, obj):
        if obj.matched_user:
            return f"{obj.matched_user.last_name} {obj.matched_user.first_name} (@{obj.matched_user.username})"
        return '—'
    matched_user_display.short_description = 'Сотрудник'


@admin.register(EmployeeLeave)
class EmployeeLeaveAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date',
                    'is_active_badge', 'is_approved', 'created_at')
    list_filter = ('leave_type', 'is_approved')
    search_fields = ('employee__username', 'employee__last_name', 'employee__first_name',
                     'employee__tab_number', 'reason')
    readonly_fields = ('created_at', 'updated_at')

    def is_active_badge(self, obj):
        if obj.is_active():
            return '<span class="badge bg-warning">Активно</span>'
        return '<span class="badge bg-secondary">Не активно</span>'
    is_active_badge.short_description = 'Статус'
    is_active_badge.allow_tags = True


@admin.register(AbsenceAlert)
class AbsenceAlertAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'host', 'login_time',
                    'is_acknowledged_badge', 'created_at')
    list_filter = ('is_acknowledged', 'leave__leave_type')
    search_fields = ('employee__username', 'employee__last_name',
                     'host__hostname', 'username')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    def leave_type(self, obj):
        if obj.leave:
            return dict(LeaveType.choices).get(obj.leave.leave_type, obj.leave.leave_type)
        return '—'
    leave_type.short_description = 'Тип отсутствия'

    def is_acknowledged_badge(self, obj):
        if obj.is_acknowledged:
            return '<span class="badge bg-success">Подтверждено</span>'
        return '<span class="badge bg-danger">Не подтверждено</span>'
    is_acknowledged_badge.short_description = 'Статус'
    is_acknowledged_badge.allow_tags = True
