from django.contrib import admin
from .models import (
    Resource, AccessGroup, AccessGrant, AccessRequest, Role, RoleGroup,
    GroupContainer, RoleGroupContainer, GroupContainerGroup, PositionRole,
    NetworkResourceDetail, SoftwareResourceDetail, RemoteAccessDetail,
    ServerResourceDetail, DatabaseResourceDetail, ApplicationResourceDetail,
    StorageResourceDetail, CloudResourceDetail, HardwareResourceDetail,
    Organization, Contract, ExternalUser,
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
    list_display = ('user', 'group', 'is_active', 'expires_at', 'granted_by')
    list_filter = ('is_active', 'grant_type')
    search_fields = ('user__last_name', 'user__first_name', 'group__name')
    raw_id_fields = ('user', 'group', 'granted_by')
    date_hierarchy = 'granted_at'


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ('requester', 'resource', 'level', 'status', 'created_at', 'approver')
    list_filter = ('status', 'level', 'resource__type')
    search_fields = ('requester__last_name', 'requester__first_name', 'resource__name', 'justification')
    raw_id_fields = ('requester', 'resource', 'approver', 'grant')
    date_hierarchy = 'created_at'


@admin.register(GroupContainer)
class GroupContainerAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'groups_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    date_hierarchy = 'created_at'
    actions = ['archive_selected', 'restore_selected']

    def archive_selected(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'Архивировано {queryset.count()} контейнеров.')
    archive_selected.short_description = 'Архивировать выбранные контейнеры'

    def restore_selected(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'Восстановлено {queryset.count()} контейнеров.')
    restore_selected.short_description = 'Восстановить выбранные контейнеры'


@admin.register(RoleGroupContainer)
class RoleGroupContainerAdmin(admin.ModelAdmin):
    list_display = ('role', 'group_container', 'added_at', 'added_by')
    list_filter = ('role__is_active', 'added_at')
    search_fields = ('role__name', 'group_container__name')
    raw_id_fields = ('role', 'group_container', 'added_by')
    date_hierarchy = 'added_at'


@admin.register(GroupContainerGroup)
class GroupContainerGroupAdmin(admin.ModelAdmin):
    list_display = ('group_container', 'access_group', 'added_at', 'added_by')
    list_filter = ('group_container__is_active', 'added_at')
    search_fields = ('group_container__name', 'access_group__name')
    raw_id_fields = ('group_container', 'access_group', 'added_by')
    date_hierarchy = 'added_at'


@admin.register(PositionRole)
class PositionRoleAdmin(admin.ModelAdmin):
    list_display = ('position', 'role', 'added_at', 'added_by')
    list_filter = ('role__is_active', 'added_at')
    search_fields = ('position__name', 'role__name')
    raw_id_fields = ('position', 'role', 'added_by')
    date_hierarchy = 'added_at'


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'inn', 'contact_name', 'contact_phone', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'inn', 'contact_name')
    date_hierarchy = 'created_at'


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('organization', 'number', 'date_from', 'date_to', 'status', 'created_at')
    list_filter = ('status', 'organization', 'created_at')
    search_fields = ('number', 'organization__name')
    raw_id_fields = ('organization',)
    date_hierarchy = 'created_at'


@admin.register(ExternalUser)
class ExternalUserAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'contract', 'user_type', 'department', 'position', 'is_active')
    list_filter = ('user_type', 'is_active', 'contract__status')
    search_fields = ('full_name', 'department', 'position', 'id_doc_no')
    raw_id_fields = ('contract',)
    date_hierarchy = 'created_at'
