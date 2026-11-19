from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Department, Position, InternalGroup, GroupMapping, ADSyncSettings, MenuSection, MenuItem


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code_1c', 'parent', 'is_active')
    search_fields = ('name', 'code_1c')


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'code_1c', 'is_active')
    search_fields = ('name', 'code_1c')


@admin.register(InternalGroup)
class InternalGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'is_system', 'created_at')
    list_filter = ('is_active', 'is_system')
    search_fields = ('name', 'code', 'description')
    prepopulated_fields = {'code': ('name',)}


class GroupMappingInline(admin.TabularInline):
    model = GroupMapping
    extra = 0
    fields = ('ad_group_name', 'ad_group_dn', 'internal_group', 'is_active')
    readonly_fields = ('ad_group_dn',)
    raw_id_fields = ('internal_group',)


@admin.register(GroupMapping)
class GroupMappingAdmin(admin.ModelAdmin):
    list_display = ('ad_group_name', 'internal_group', 'is_active', 'created_at')
    list_filter = ('is_active', 'internal_group')
    search_fields = ('ad_group_name', 'ad_group_description')
    raw_id_fields = ('internal_group',)
    inlines = []


@admin.register(ADSyncSettings)
class ADSyncSettingsAdmin(admin.ModelAdmin):
    list_display = ('ad_server', 'ad_port', 'ad_use_ssl', 'is_enabled', 'last_sync', 'updated_at')
    list_filter = ('is_enabled', 'ad_use_ssl', 'sync_on_login')
    fields = (
        'ad_server', 'ad_port', 'ad_use_ssl', 'ad_base_dn',
        'ad_bind_dn', 'ad_bind_password',
        'ad_user_search_base', 'ad_group_search_base',
        'ad_user_object_class', 'ad_user_samaccountname_field',
        'ad_user_memberof_field',
        'ad_group_object_class', 'ad_group_cn_field',
        'ad_group_samaccountname_field',
        'sync_on_login', 'sync_interval_hours',
        'last_sync', 'is_enabled',
    )
    readonly_fields = ('last_sync',)


@admin.register(MenuSection)
class MenuSectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    prepopulated_fields = {'code': ('name',)}
    list_editable = ('order', 'is_active')
    ordering = ('order', 'name')


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0
    fields = ('name', 'url_name', 'url_pattern', 'icon', 'order', 'is_active')
    list_display = ('name', 'url_name', 'order', 'is_active')
    ordering = ('order', 'name')


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'section', 'url_name', 'order', 'is_active')
    list_filter = ('is_active', 'section')
    search_fields = ('name', 'url_name', 'url_pattern')
    list_editable = ('order', 'is_active')
    ordering = ('section__order', 'order', 'name')


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Кадровые данные', {
            'fields': ('patronymic', 'corporate_phone', 'personal_phone', 'snils',
                       'corporate_email', 'personal_email',
                       'department', 'position', 'employee_code_1c'),
        }),
        ('Внутренние группы', {
            'fields': ('internal_groups',),
        }),
    )
    list_display = ('username', 'last_name', 'first_name', 'patronymic',
                    'corporate_phone', 'department', 'position')
    filter_horizontal = ('internal_groups', 'groups', 'user_permissions')
