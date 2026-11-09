from django.contrib import admin
from .models import (
    Category, Scenario, Branch, Step,
    Run, StepRun, Answer, DbValue, Log,
    Role, EmployeeRole,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'version', 'is_active', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'scenario', 'created_at']
    list_filter = ['scenario']
    search_fields = ['name', 'code']


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    list_display = ['step_order', 'prev_result_code', 'branch', 'deadline_min']
    list_filter = ['branch__scenario']
    search_fields = ['message_text']


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ['scenario', 'started_by', 'status', 'started_at', 'completed_at']
    list_filter = ['status', 'scenario__category']
    search_fields = ['scenario__name']
    readonly_fields = ['started_at', 'completed_at']


@admin.register(StepRun)
class StepRunAdmin(admin.ModelAdmin):
    list_display = ['run', 'step', 'recipient', 'status', 'sent_at']
    list_filter = ['status', 'run']
    search_fields = ['recipient__last_name', 'recipient__first_name']
    readonly_fields = ['sent_at']


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['run', 'step_run', 'employee', 'received_at']
    list_filter = ['run']
    search_fields = ['employee__last_name', 'employee__first_name']
    readonly_fields = ['received_at']


@admin.register(DbValue)
class DbValueAdmin(admin.ModelAdmin):
    list_display = ['run', 'employee', 'key']
    list_filter = ['run']
    search_fields = ['key', 'value']


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ['run', 'event_type', 'created_at']
    list_filter = ['event_type', 'run']
    search_fields = ['payload_json']
    readonly_fields = ['created_at']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(EmployeeRole)
class EmployeeRoleAdmin(admin.ModelAdmin):
    list_display = ['employee', 'role', 'scope_department']
    list_filter = ['role', 'scope_department']
    search_fields = ['employee__last_name', 'employee__first_name']
