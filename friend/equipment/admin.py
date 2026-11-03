from django.contrib import admin
from .models import (
    Equipment, EquipmentAssignment, EquipmentMOLAssignment,
    EQUIPMENT_CATEGORIES, EQUIPMENT_SUBTYPES,
)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = (
        'inventory_number', 'name', 'category', 'subtype', 'brand', 'model',
        'assigned_user', 'hostname', 'ip_address', 'is_active', 'archived',
        'antivirus_active', 'last_scan', 'location',
    )
    list_filter = (
        'category', 'subtype', 'is_active', 'archived', 'antivirus_active',
        'os', 'status',
    )
    search_fields = (
        'inventory_number', 'serial_number', 'name', 'brand', 'model',
        'hostname', 'ip_address', 'mac_address', 'cpu',
    )
    readonly_fields = ('created_at', 'updated_at', 'last_scan')
    list_select_related = ('assigned_user', 'responsible_user')

    fieldsets = (
        ('Инвентаризация', {
            'fields': (
                'inventory_number', 'serial_number', 'name', 'brand', 'model',
                'assigned_user', 'responsible_user',
            ),
        }),
        ('Тип оборудования', {
            'fields': ('category', 'subtype'),
        }),
        ('Сетевая информация', {
            'fields': ('hostname', 'mac_address', 'ip_address'),
        }),
        ('Аппаратное обеспечение', {
            'fields': ('cpu', 'ram_gb', 'storage_gb'),
        }),
        ('Программное обеспечение', {
            'fields': ('os', 'os_version', 'antivirus_engine', 'antivirus_active'),
        }),
        ('Специфичные поля', {
            'fields': (
                'screen_size', 'resolution', 'printer_status',
                'camera_count', 'phone_number', 'extension',
            ),
            'classes': ('collapse',),
        }),
        ('Расположение', {
            'fields': ('location', 'place'),
        }),
        ('SIEM', {
            'fields': ('last_scan',),
            'classes': ('collapse',),
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def secured_badge(self, obj):
        if obj.is_secured:
            return '<span class="badge bg-success"><i class="bi bi-shield-check"></i></span>'
        return '<span class="badge bg-danger"><i class="bi bi-shield-x"></i></span>'
    secured_badge.short_description = 'Защита'
    secured_badge.allow_tags = True


@admin.register(EquipmentAssignment)
class EquipmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'equipment', 'equipment_type_label', 'assigned_at', 'is_active', 'is_returned')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'notes')
    readonly_fields = ('assigned_at', 'returned_at')
    date_hierarchy = 'assigned_at'

    def equipment_type_label(self, obj):
        return obj.equipment.get_subtype_display()
    equipment_type_label.short_description = 'Тип'


@admin.register(EquipmentMOLAssignment)
class EquipmentMOLAssignmentAdmin(admin.ModelAdmin):
    list_display = ('mol', 'equipment', 'equipment_type_label', 'assigned_at', 'is_active', 'is_returned')
    list_filter = ('is_active',)
    search_fields = ('mol__username', 'mol__first_name', 'mol__last_name', 'notes')
    readonly_fields = ('assigned_at', 'returned_at')
    date_hierarchy = 'assigned_at'

    def equipment_type_label(self, obj):
        return obj.equipment.get_subtype_display()
    equipment_type_label.short_description = 'Тип'
