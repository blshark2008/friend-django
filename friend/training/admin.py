from django.contrib import admin
from .models import (
    TrainingCategory, TrainingType,
    Training, SkillspaceGroup, TrainingEnrollment,
)


@admin.register(TrainingCategory)
class TrainingCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(TrainingType)
class TrainingTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'goal_type', 'is_active', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['name']
    ordering = ['name']

    def goal_type(self, obj):
        return obj.category.name if obj.category else '—'
    goal_type.short_description = 'Категория'


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ['title', 'training_type', 'category', 'status', 'is_active', 'created_at']
    list_filter = ['status', 'is_active', 'training_type__category']
    search_fields = ['title']
    ordering = ['-created_at']

    def category(self, obj):
        return obj.training_type.category.name if obj.training_type.category else '—'
    category.short_description = 'Категория'


@admin.register(SkillspaceGroup)
class SkillspaceGroupAdmin(admin.ModelAdmin):
    list_display = ['course', 'name', 'students_count', 'last_synced']
    list_filter = ['course']


@admin.register(TrainingEnrollment)
class TrainingEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'training', 'status', 'score', 'enrolled_at']
    list_filter = ['status', 'training__training_type__category']
    search_fields = ['user__last_name', 'user__first_name', 'training__title']
    ordering = ['-enrolled_at']