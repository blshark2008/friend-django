from django.contrib import admin
from .models import (
    Equipment, EquipmentAssignment, EquipmentMOLAssignment,
    EquipmentCategory,
    EquipmentMovement, EquipmentRepair, EquipmentUpgrade,
    EquipmentDecommissionRecord,
)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = (
        'inventory_number', 'name', 'category', 'subcategory', 'brand', 'model',
        'assigned_user', 'hostname', 'ip_address', 'is_active', 'archived',
        'antivirus_active', 'last_scan', 'location', 'acquisition_date',
        'decommission_date', 'status',
    )
    list_filter = (
        'category', 'subcategory', 'is_active', 'archived', 'antivirus_active',
        'os', 'status', 'decommission_date',
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
            'fields': ('category', 'subcategory'),
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
        ('Бухгалтерская информация', {
            'fields': (
                'acquisition_date', 'acquisition_cost', 'initial_number',
                'useful_life_months', 'depreciation_method',
            ),
            'classes': ('collapse',),
        }),
        ('Информация о списании', {
            'fields': (
                'decommission_date', 'decommission_act', 'decommission_notes',
                'decommissioned_by',
            ),
            'classes': ('collapse',),
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


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_top_level', 'is_active', 'equipment_count', 'created_at')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug', 'code_1c')
    readonly_fields = ('created_at', 'updated_at', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(EquipmentAssignment)
class EquipmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'equipment', 'equipment_type_label', 'assigned_at', 'is_active', 'is_returned')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'notes')
    readonly_fields = ('assigned_at', 'returned_at')
    date_hierarchy = 'assigned_at'

    def equipment_type_label(self, obj):
        return obj.equipment.type_label
    equipment_type_label.short_description = 'Тип'


@admin.register(EquipmentMOLAssignment)
class EquipmentMOLAssignmentAdmin(admin.ModelAdmin):
    list_display = ('mol', 'equipment', 'equipment_type_label', 'assigned_at', 'is_active', 'is_returned')
    list_filter = ('is_active',)
    search_fields = ('mol__username', 'mol__first_name', 'mol__last_name', 'notes')
    readonly_fields = ('assigned_at', 'returned_at')
    date_hierarchy = 'assigned_at'

    def equipment_type_label(self, obj):
        return obj.equipment.type_label
    equipment_type_label.short_description = 'Тип'


@admin.register(EquipmentMovement)
class EquipmentMovementAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'from_location', 'to_location', 'move_date', 'moved_by', 'move_datetime')
    list_filter = ('move_date',)
    search_fields = ('equipment__inventory_number', 'from_location', 'to_location', 'notes')
    readonly_fields = ('move_datetime', 'created_at')
    date_hierarchy = 'move_datetime'
    list_select_related = ('equipment', 'moved_by')


@admin.register(EquipmentRepair)
class EquipmentRepairAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'repair_type', 'result', 'service_company', 'cost', 'start_date', 'end_date', 'created_at')
    list_filter = ('repair_type', 'result', 'created_at')
    search_fields = ('equipment__inventory_number', 'description', 'service_company')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_select_related = ('equipment',)


@admin.register(EquipmentUpgrade)
class EquipmentUpgradeAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'result', 'cost', 'performed_date', 'created_at')
    list_filter = ('result', 'created_at')
    search_fields = ('equipment__inventory_number', 'description', 'old_specs', 'new_specs')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_select_related = ('equipment',)


@admin.register(EquipmentDecommissionRecord)
class EquipmentDecommissionRecordAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'act_number', 'act_date', 'reason', 'created_at')
    list_filter = ('act_date', 'created_at')
    search_fields = ('equipment__inventory_number', 'act_number', 'reason', 'commission')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('equipment',)
