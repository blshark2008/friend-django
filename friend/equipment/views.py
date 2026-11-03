import json
import logging
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect, Http404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.db.models import Q, Count, Prefetch
from django.urls import reverse
from django.http import JsonResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from .models import (
    Equipment, EquipmentAssignment, EquipmentMOLAssignment, EquipmentFieldSetting,
    EQUIPMENT_CATEGORIES, EQUIPMENT_SUBTYPES, get_subtypes_for_category,
    EQUIPMENT_CATEGORY_COMPUTER, EQUIPMENT_CATEGORY_PRINTER, EQUIPMENT_CATEGORY_PERIPHERY,
    COMPUTER_SUBTYPE_DESKTOP, COMPUTER_SUBTYPE_LAPTOP, COMPUTER_SUBTYPE_TABLET,
    COMPUTER_SUBTYPE_MONITOR, COMPUTER_SUBTYPE_SERVER,
    OTHER_SUBTYPE_VKS, EQUIPMENT_STATUS_CHOICES,
    EQUIPMENT_FIELD_DEFINITIONS,
)
from .forms import (
    EquipmentForm, SimpleEquipmentForm, AssignUserForm,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Class-based views
# ============================================================================

class EquipmentListView(ListView):
    """Список оборудования по типу (класс-бейз view)."""
    model = Equipment
    template_name = 'equipment/computer_list.html'
    context_object_name = 'equipment_list'
    equipment_type = None

    def get_queryset(self):
        qs = Equipment.objects.filter(archived=False).select_related(
            'assigned_user', 'responsible_user'
        )
        if self.equipment_type:
            qs = qs.filter(category=self.equipment_type)
        return qs.order_by('-is_active', 'category', 'subtype', 'inventory_number')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['equipment_type'] = self.equipment_type
        context['computers_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_DESKTOP, archived=False).count()
        context['laptops_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_LAPTOP, archived=False).count()
        context['tablets_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_TABLET, archived=False).count()
        context['monitors_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_MONITOR, archived=False).count()
        context['servers_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_SERVER, archived=False).count()
        context['printers_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_PRINTER, archived=False).count()
        context['medical_count'] = Equipment.objects.filter(subtype=OTHER_SUBTYPE_VKS, archived=False).count()
        context['peripherals_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_PERIPHERY, archived=False).count()
        context['phones_count'] = Equipment.objects.filter(subtype='inkjet', archived=False).count()
        context['vks_count'] = Equipment.objects.filter(subtype=OTHER_SUBTYPE_VKS, archived=False).count()
        return context


class ComputerListView(ListView):
    """Список компьютерного оборудования."""
    model = Equipment
    template_name = 'equipment/computer_list.html'
    context_object_name = 'equipment_list'

    def get_queryset(self):
        qs = Equipment.objects.filter(
            archived=False,
            category=EQUIPMENT_CATEGORY_COMPUTER
        ).select_related('assigned_user', 'responsible_user')
        return qs.order_by('-is_active', 'subtype', 'inventory_number')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['computers_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_DESKTOP, archived=False).count()
        context['laptops_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_LAPTOP, archived=False).count()
        context['tablets_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_TABLET, archived=False).count()
        context['monitors_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_MONITOR, archived=False).count()
        context['servers_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_SERVER, archived=False).count()
        context['printers_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_PRINTER, archived=False).count()
        context['medical_count'] = Equipment.objects.filter(subtype=OTHER_SUBTYPE_VKS, archived=False).count()
        context['peripherals_count'] = Equipment.objects.filter(category=EQUIPMENT_CATEGORY_PERIPHERY, archived=False).count()
        context['phones_count'] = Equipment.objects.filter(subtype='inkjet', archived=False).count()
        context['vks_count'] = Equipment.objects.filter(subtype=OTHER_SUBTYPE_VKS, archived=False).count()
        return context


# ============================================================================
# Список техники
# ============================================================================

@login_required
def equipment_list(request):
    """Общий список всего оборудования."""
    equipment_qs = Equipment.objects.filter(archived=False).select_related(
        'assigned_user', 'responsible_user'
    )

    # Фильтры
    category = request.GET.get('category')
    subtype = request.GET.get('subtype')
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status')
    location = request.GET.get('location', '').strip()

    if category:
        equipment_qs = equipment_qs.filter(category=category)
    if subtype:
        equipment_qs = equipment_qs.filter(subtype=subtype)
    if search:
        equipment_qs = equipment_qs.filter(
            Q(inventory_number__icontains=search)
            | Q(serial_number__icontains=search)
            | Q(name__icontains=search)
            | Q(brand__icontains=search)
            | Q(model__icontains=search)
            | Q(hostname__icontains=search)
            | Q(ip_address__icontains=search)
            | Q(location__icontains=search)
        )
    if status:
        equipment_qs = equipment_qs.filter(status=status)
    if location:
        equipment_qs = equipment_qs.filter(location__icontains=location)

    equipment_qs = equipment_qs.order_by('-is_active', 'category', 'subtype', 'inventory_number')

    total_count = equipment_qs.count()

    # Counts for sidebar badges
    computers_count = Equipment.objects.filter(
        category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_DESKTOP, archived=False
    ).count()
    laptops_count = Equipment.objects.filter(
        category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_LAPTOP, archived=False
    ).count()
    tablets_count = Equipment.objects.filter(
        category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_TABLET, archived=False
    ).count()
    monitors_count = Equipment.objects.filter(
        category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_MONITOR, archived=False
    ).count()
    servers_count = Equipment.objects.filter(
        category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_SERVER, archived=False
    ).count()
    printers_count = Equipment.objects.filter(
        category=EQUIPMENT_CATEGORY_PRINTER, archived=False
    ).count()
    medical_count = Equipment.objects.filter(
        subtype=OTHER_SUBTYPE_VKS, archived=False
    ).count()
    peripherals_count = Equipment.objects.filter(
        category=EQUIPMENT_CATEGORY_PERIPHERY, archived=False
    ).count()
    phones_count = Equipment.objects.filter(
        subtype='inkjet', archived=False
    ).count()
    vks_count = Equipment.objects.filter(
        subtype=OTHER_SUBTYPE_VKS, archived=False
    ).count()

    context = {
        'equipment_list': equipment_qs,
        'total_count': total_count,
        'categories': EQUIPMENT_CATEGORIES,
        'subtypes': EQUIPMENT_SUBTYPES,
        'current_category': category,
        'current_subtype': subtype,
        'current_search': search,
        'current_status': status,
        'current_location': location,
        'computers_count': computers_count,
        'laptops_count': laptops_count,
        'tablets_count': tablets_count,
        'monitors_count': monitors_count,
        'servers_count': servers_count,
        'printers_count': printers_count,
        'medical_count': medical_count,
        'peripherals_count': peripherals_count,
        'phones_count': phones_count,
        'vks_count': vks_count,
    }
    return render(request, 'equipment/equipment_list.html', context)


# ============================================================================
# Справочник категорий
# ============================================================================

@login_required
def categories_reference(request):
    """Справочник категорий и подтипов оборудования."""
    # Статистика по категориям
    category_stats = {}
    for cat_value, cat_label in EQUIPMENT_CATEGORIES:
        count = Equipment.objects.filter(category=cat_value, archived=False).count()
        subtypes = get_subtypes_for_category(cat_value)
        subtype_counts = {}
        for sub_value, sub_label in subtypes:
            subtype_count = Equipment.objects.filter(
                category=cat_value, subtype=sub_value, archived=False
            ).count()
            subtype_counts[sub_label] = subtype_count
        category_stats[cat_label] = {
            'value': cat_value,
            'count': count,
            'subtypes': subtype_counts,
        }

    # Статистика по статусам
    status_stats = {}
    for status_value, status_label in EQUIPMENT_STATUS_CHOICES:
        count = Equipment.objects.filter(status=status_value, archived=False).count()
        status_stats[status_label] = count

    # Статистика по закреплениям
    assigned_count = Equipment.objects.filter(
        archived=False, assigned_user__isnull=False
    ).count()
    unassigned_count = Equipment.objects.filter(
        archived=False, assigned_user__isnull=True
    ).count()

    # Статистика по защите
    secured_count = Equipment.objects.filter(
        archived=False, antivirus_active=True
    ).count()
    unsecured_count = Equipment.objects.filter(
        archived=False, antivirus_active=False
    ).count()

    context = {
        'category_stats': category_stats,
        'status_stats': status_stats,
        'assigned_count': assigned_count,
        'unassigned_count': unassigned_count,
        'secured_count': secured_count,
        'unsecured_count': unsecured_count,
        'computers_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_DESKTOP, archived=False).count(),
        'laptops_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_LAPTOP, archived=False).count(),
        'tablets_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_TABLET, archived=False).count(),
        'monitors_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_MONITOR, archived=False).count(),
        'servers_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_SERVER, archived=False).count(),
        'printers_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_PRINTER, archived=False).count(),
        'medical_count': Equipment.objects.filter(subtype=OTHER_SUBTYPE_VKS, archived=False).count(),
        'peripherals_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_PERIPHERY, archived=False).count(),
        'phones_count': Equipment.objects.filter(subtype='inkjet', archived=False).count(),
        'vks_count': Equipment.objects.filter(subtype=OTHER_SUBTYPE_VKS, archived=False).count(),
    }
    return render(request, 'equipment/categories_reference.html', context)


# ============================================================================
# Стубы для существующих URL (предыдущая реализация отсутствует в views.py)
# ============================================================================

def _sidebar_counts():
    """Возвращает словарь счётчиков для бейджей в сайдбаре."""
    return {
        'computers_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_DESKTOP, archived=False).count(),
        'laptops_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_LAPTOP, archived=False).count(),
        'tablets_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_TABLET, archived=False).count(),
        'monitors_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_MONITOR, archived=False).count(),
        'servers_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_COMPUTER, subtype=COMPUTER_SUBTYPE_SERVER, archived=False).count(),
        'printers_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_PRINTER, archived=False).count(),
        'medical_count': Equipment.objects.filter(subtype=OTHER_SUBTYPE_VKS, archived=False).count(),
        'peripherals_count': Equipment.objects.filter(category=EQUIPMENT_CATEGORY_PERIPHERY, archived=False).count(),
        'phones_count': Equipment.objects.filter(subtype='inkjet', archived=False).count(),
        'vks_count': Equipment.objects.filter(subtype=OTHER_SUBTYPE_VKS, archived=False).count(),
    }

def export_equipment_to_excel(request):
    """Стуб: экспорт оборудования в Excel."""
    return render(request, 'equipment/equipment_list.html', {**_sidebar_counts(), 'equipment_list': Equipment.objects.none()})

def dashboard(request):
    """Стуб: дашборд."""
    return render(request, 'equipment/dashboard.html', _sidebar_counts())

def department_equipment(request, department_id):
    """Стуб: оборудование подразделения."""
    return render(request, 'equipment/department_equipment.html', _sidebar_counts())

def upload_os_csv(request):
    """Стуб: загрузка CSV."""
    return render(request, 'equipment/upload_os_csv.html', _sidebar_counts())

def equipment_add(request, equipment_type):
    """Добавление оборудования с учётом настроек полей."""
    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Оборудование успешно добавлено')
            return redirect('equipment:equipment_list')
    else:
        form = EquipmentForm()
    
    type_labels = dict(EQUIPMENT_SUBTYPES)
    type_label = type_labels.get(equipment_type, equipment_type)
    return render(request, 'equipment/equipment_add.html', {
        **_sidebar_counts(),
        'form': form,
        'type_label': type_label,
    })

def equipment_edit(request, equipment_type, pk):
    """Редактирование оборудования с учётом настроек полей."""
    equipment = get_object_or_404(Equipment, pk=pk, archived=False)
    
    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=equipment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Оборудование успешно обновлено')
            return redirect('equipment:detail', equipment_type=equipment.category, pk=equipment.pk)
    else:
        form = EquipmentForm(instance=equipment)
    
    type_labels = dict(EQUIPMENT_SUBTYPES)
    type_label = type_labels.get(equipment_type, equipment_type)
    return render(request, 'equipment/equipment_edit_simple.html', {
        **_sidebar_counts(),
        'form': form,
        'instance': equipment,
        'equipment_type': equipment.category,
        'assigned_user': equipment.assigned_user,
        'mol_assignment': equipment.mol_assignments.filter(is_active=True).first(),
        'type_label': type_label,
    })

def equipment_archive(request, equipment_type, pk):
    """Стуб: архивирование."""
    return redirect('equipment:equipment_list')

def assign_user_generic(request):
    """Стуб: назначение пользователя."""
    return render(request, 'equipment/equipment_list.html', _sidebar_counts())

def assign_user(request, equipment_type, pk):
    """Стуб: назначение пользователя на оборудование."""
    return render(request, 'equipment/equipment_list.html', _sidebar_counts())

def change_assigned_user_ajax(request, equipment_type, pk):
    """Стуб: AJAX назначение пользователя."""
    return JsonResponse({'status': 'ok'})

def clear_assigned_user(request, equipment_type, pk):
    """Стуб: освобождение от пользователя."""
    return redirect('equipment:equipment_list')

def lookup_user_by_serial(request):
    """Стуб: поиск пользователя по серийному."""
    return JsonResponse({})

def search_users_ajax(request):
    """Стуб: AJAX поиск пользователей."""
    return JsonResponse({})

def quick_assign_users(request):
    """Стуб: быстрое назначение."""
    return JsonResponse({'status': 'ok'})

def equipment_detail(request, equipment_type, pk):
    """Детальная информация об оборудовании с учётом настроек полей."""
    equipment = get_object_or_404(Equipment, pk=pk, archived=False)
    visible_fields = equipment.get_visible_fields(for_edit=False)
    return render(request, 'equipment/equipment_detail.html', {
        **_sidebar_counts(),
        'instance': equipment,
        'visible_fields': visible_fields,
    })

def update_from_siem(request, equipment_type, pk):
    """Стуб: обновление из SIEM."""
    return JsonResponse({'status': 'ok'})

def redirect_to_siem_host(request, serial):
    """Стуб: редирект на SIEM."""
    return redirect(f'/siem/hosts/?serial={serial}')

def move_equipment(request, pk):
    """Стуб: перемещение."""
    return redirect('equipment:equipment_list')

def batch_archive(request):
    """Стуб: массовое архивирование."""
    return redirect('equipment:equipment_list')

def batch_move(request):
    """Стуб: массовое перемещение."""
    return redirect('equipment:equipment_list')

def assign_mol(request, equipment_type, pk):
    """Стуб: назначение МОЛ."""
    return render(request, 'equipment/equipment_list.html', _sidebar_counts())

def assign_mol_ajax(request, equipment_type, pk):
    """Стуб: AJAX назначение МОЛ."""
    return JsonResponse({'status': 'ok'})

def change_responsible_user_ajax(request, equipment_type, pk):
    """Стуб: AJAX изменение ответственного."""
    return JsonResponse({'status': 'ok'})

def clear_responsible_user(request, equipment_type, pk):
    """Стуб: освобождение от МОЛ."""
    return redirect('equipment:equipment_list')

def assign_mol_batch(request):
    """Стуб: массовое назначение МОЛ."""
    return redirect('equipment:equipment_list')

def equipment_inventory(request):
    """Стуб: инвентаризация."""
    return render(request, 'equipment/inventory.html', _sidebar_counts())

def equipment_inventory_detail(request, equipment_type, pk):
    """Стуб: детальная инвентаризация."""
    return render(request, 'equipment/inventory.html', _sidebar_counts())


# ============================================================================
# Управление настройками полей
# ============================================================================

@login_required
def field_settings(request):
    """Управление настройками отображения полей для подтипов оборудования."""
    if request.method == 'POST':
        # Обновляем настройки
        for field_def in EQUIPMENT_FIELD_DEFINITIONS:
            field_name = field_def[0]
            field_label = field_def[1]
            field_group = field_def[2]
            
            for subtype_value, subtype_label in EQUIPMENT_SUBTYPES:
                is_visible = request.POST.get(f'visible_{subtype_value}_{field_name}', 'on') == 'on'
                is_editable = request.POST.get(f'editable_{subtype_value}_{field_name}', 'on') == 'on'
                
                setting, created = EquipmentFieldSetting.objects.get_or_create(
                    subtype=subtype_value,
                    field_name=field_name,
                    defaults={
                        'field_label': field_label,
                        'field_group': field_group,
                        'is_visible': is_visible,
                        'is_editable': is_editable,
                    }
                )
                if not created:
                    setting.field_label = field_label
                    setting.field_group = field_group
                    setting.is_visible = is_visible
                    setting.is_editable = is_editable
                    setting.save()
        
        messages.success(request, 'Настройки полей сохранены')
        return redirect('equipment:field_settings')
    
    # Загружаем текущие настройки
    settings_data = {}
    for subtype_value, subtype_label in EQUIPMENT_SUBTYPES:
        settings = EquipmentFieldSetting.objects.filter(subtype=subtype_value)
        settings_map = {s.field_name: s for s in settings}
        settings_data[subtype_value] = {
            'label': subtype_label,
            'fields': [],
        }
        
        for field_def in EQUIPMENT_FIELD_DEFINITIONS:
            field_name = field_def[0]
            field_label = field_def[1]
            field_group = field_def[2]
            
            setting = settings_map.get(field_name)
            if setting:
                settings_data[subtype_value]['fields'].append({
                    'name': field_name,
                    'label': field_label,
                    'group': field_group,
                    'is_visible': setting.is_visible,
                    'is_editable': setting.is_editable,
                })
            else:
                settings_data[subtype_value]['fields'].append({
                    'name': field_name,
                    'label': field_label,
                    'group': field_group,
                    'is_visible': True,
                    'is_editable': True,
                })
    
    context = {
        **_sidebar_counts(),
        'settings_data': settings_data,
        'field_definitions': EQUIPMENT_FIELD_DEFINITIONS,
    }
    return render(request, 'equipment/field_settings.html', context)
