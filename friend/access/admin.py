from django.contrib import admin
from .models import (
    Resource, AccessGroup, AccessGrant, AccessRequest, Role, RoleGroup,
    NetworkResourceDetail, SoftwareResourceDetail, RemoteAccessDetail,
    ServerResourceDetail, DatabaseResourceDetail, ApplicationResourceDetail,
    StorageResourceDetail, CloudResourceDetail, HardwareResourceDetail,
)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'owner', 'is_active', 'last_audit_date', 'created_at')
    list_filter = ('type', 'is_active', 'owner', 'last_audit_date')
    search_fields = ('name', 'description')
    date_hierarchy = 'created_at'
    actions = ['archive_selected', 'restore_selected']

    def archive_selected(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'Архивировано {queryset.count()} ролей.')
    archive_selected.short_description = 'Архивировать выбранные роли'

    def restore_selected(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'Восстановлено {queryset.count()} ролей.')
    restore_selected.short_description = 'Восстановить выбранные роли'


@admin.register(RoleGroup)
class RoleGroupAdmin(admin.ModelAdmin):
    list_display = ('role', 'access_group', 'added_at', 'added_by')
    list_filter = ('role__is_active', 'added_at')
    search_fields = ('role__name', 'access_group__name')
    raw_id_fields = ('role', 'access_group', 'added_by')
    date_hierarchy = 'added_at'


@admin.register(AccessGrant)
class AccessGrantAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'resource', 'level', 'is_active', 'expires_at', 'granted_by')
    list_filter = ('level', 'is_active', 'grant_type', 'resource__type')
    search_fields = ('user__last_name', 'user__first_name', 'resource__name', 'group__name')
    raw_id_fields = ('user', 'group', 'resource', 'granted_by')
    date_hierarchy = 'granted_at'


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ('requester', 'resource', 'level', 'status', 'created_at', 'approver')
    list_filter = ('status', 'level', 'resource__type')
    search_fields = ('requester__last_name', 'requester__first_name', 'resource__name', 'justification')
    raw_id_fields = ('requester', 'resource', 'approver', 'grant')
    date_hierarchy = 'created_at'
