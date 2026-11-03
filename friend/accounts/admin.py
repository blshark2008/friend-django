from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Department, Position


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code_1c', 'parent', 'is_active')
    search_fields = ('name', 'code_1c')


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'code_1c', 'is_active')
    search_fields = ('name', 'code_1c')


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Кадровые данные', {
            'fields': ('patronymic', 'corporate_phone', 'personal_phone', 'snils',
                       'corporate_email', 'personal_email',
                       'department', 'position', 'employee_code_1c'),
        }),
    )
    list_display = ('username', 'last_name', 'first_name', 'patronymic',
                    'corporate_phone', 'department', 'position')
