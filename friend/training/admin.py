from django.contrib import admin
from .models import TrainingType, Training, TrainingEnrollment, TrainingGoal, GoalTrainingType


@admin.register(TrainingGoal)
class TrainingGoalAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'training_types_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


class GoalTrainingTypeInline(admin.TabularInline):
    model = GoalTrainingType
    extra = 0
    readonly_fields = ['created_at']


@admin.register(TrainingType)
class TrainingTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'skillspace_course_id', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


class TrainingEnrollmentInline(admin.TabularInline):
    model = TrainingEnrollment
    readonly_fields = ['status', 'score', 'enrolled_at', 'completed_at']
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ['title', 'training_type', 'status', 'start_date', 'end_date', 'is_active', 'created_at']
    list_filter = ['training_type', 'status', 'is_active', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'last_sync_at']
    inlines = [TrainingEnrollmentInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)


@admin.register(TrainingEnrollment)
class TrainingEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'training', 'status', 'score', 'enrolled_at', 'completed_at']
    list_filter = ['status', 'enrolled_at', 'completed_at']
    search_fields = ['user__last_name', 'user__first_name', 'user__corporate_email', 'training__title']
    readonly_fields = ['enrolled_at', 'created_at', 'updated_at']
    list_select_related = ['user', 'training']
