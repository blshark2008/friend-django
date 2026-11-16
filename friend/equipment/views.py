import csv
import io
import json
import logging
import re
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect, Http404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
User = get_user_model()
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.db.models import Q, Count, Prefetch
from django.urls import reverse
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from .models import (
    Equipment, EquipmentAssignment, EquipmentMOLAssignment, EquipmentFieldSetting,
    EquipmentCategory, ExcludeKeyword, FilterKeyword, EQUIPMENT_STATUS_CHOICES,
    EQUIPMENT_SUBTYPES,
    City, Building, Floor, Room,
)
from .forms import (
    EquipmentForm, SimpleEquipmentForm, AssignUserForm,
    CityForm, BuildingForm, FloorForm, RoomForm,
)
from accounts.models import Department


# ============================================================================
# Фильтр по наименованию — определяет, относится ли позиция к интересующей
# технике (компьютерное, периферия, сеть, связь, принтеры, видео, мед.)
# Исключает: мебель, ПО, расходники, книги, мед. инструменты и т.д.
# ============================================================================

def _get_exclude_keywords():
    """Получает ключевые слова исключений из базы данных."""
    return list(
        ExcludeKeyword.objects.filter(is_active=True)
        .values_list('keyword', flat=True)
        .order_by('keyword')
    )


def _get_filter_keywords():
    """Получает ключевые слова фильтрации из базы данных, сгруппированные по категориям."""
    keywords = FilterKeyword.objects.filter(is_active=True).values_list('category', 'keyword')
    result = {}
    for category, keyword in keywords:
        if category not in result:
            result[category] = []
        result[category].append(keyword)
    return result


def classify_by_name(name):
    """
    Определяет категорию техники по наименованию.
    Возвращает список категорий или пустой список, если не попадает.
    Применяет второй уровень фильтрации — исключения.
    """
    if not name:
        return []

    # Второй уровень: проверяем исключения
    name_lower = name.lower()
    exclude_kws = _get_exclude_keywords()
    for kw in exclude_kws:
        if re.search(kw, name_lower):
            return []  # Позиция исключена
    
    # Первый уровень: ищем по ключевым словам категорий из БД
    matched = []
    filter_kws = _get_filter_keywords()
    
    for category, keywords in filter_kws.items():
        for kw in keywords:
            if re.search(kw, name_lower):
                matched.append(category)
                break
    
    return matched

logger = logging.getLogger(__name__)


def _find_equipment_by_inventory(inventory_number):
    """Находит оборудование по инвентарному номеру с несколькими вариантами нормализации."""
    if not inventory_number:
        return None
    
    # Варианты нормализации инвентарного номера
    variations = [
        inventory_number,  # Точное совпадение
        inventory_number.replace(' ', ''),  # Убираем пробелы
        inventory_number.replace('-', ''),  # Убираем дефисы
        inventory_number.replace(' ', '').replace('-', ''),  # Убираем пробелы и дефисы
        inventory_number.strip(),  # Убираем пробелы по краям
    ]
    
    # Убираем дубликаты, сохраняя порядок
    seen = set()
    unique_variations = []
    for v in variations:
        if v not in seen and v:
            seen.add(v)
            unique_variations.append(v)
    
    # Ищем по всем вариантам
    for inv in unique_variations:
        equipment = Equipment.objects.filter(
            inventory_number=inv, archived=False
        ).first()
        if equipment:
            return equipment
    
    return None


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
            'assigned_user', 'responsible_user', 'category', 'subcategory'
        )
        if self.equipment_type:
            # equipment_type может быть slug категории
            cat = EquipmentCategory.objects.filter(slug=self.equipment_type, is_active=True).first()
            if cat:
                if cat.is_top_level:
                    qs = qs.filter(category=cat)
                else:
                    qs = qs.filter(subcategory=cat)
        return qs.order_by('-is_active', 'category', 'subcategory', 'inventory_number')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['equipment_type'] = self.equipment_type
        context['computers_count'] = Equipment.objects.filter(
            subcategory__slug='desktop', archived=False).count()
        context['laptops_count'] = Equipment.objects.filter(
            subcategory__slug='laptop', archived=False).count()
        context['tablets_count'] = Equipment.objects.filter(
            subcategory__slug='tablet', archived=False).count()
        context['monitors_count'] = Equipment.objects.filter(
            subcategory__slug='monitor', archived=False).count()
        context['servers_count'] = Equipment.objects.filter(
            subcategory__slug='server', archived=False).count()
        context['printers_count'] = Equipment.objects.filter(
            category__slug='printers_top', archived=False).count()
        context['medical_count'] = Equipment.objects.filter(
            category__slug='medical_top', archived=False).count()
        context['peripherals_count'] = Equipment.objects.filter(
            category__slug='periphery_top', archived=False).count()
        context['phones_count'] = Equipment.objects.filter(
            subcategory__slug__in=['voip_phone', 'system_phone', 'cordless_phone', 'cellular_phone'],
            archived=False).count()
        context['vks_count'] = Equipment.objects.filter(
            subcategory__slug='vks', archived=False).count()
        return context


class ComputerListView(ListView):
    """Список компьютерного оборудования."""
    model = Equipment
    template_name = 'equipment/computer_list.html'
    context_object_name = 'equipment_list'

    def get_queryset(self):
        cat = EquipmentCategory.objects.filter(slug='computer_top', is_active=True).first()
        qs = Equipment.objects.filter(
            archived=False,
            category=cat
        ).select_related('assigned_user', 'responsible_user', 'category', 'subcategory')
        return qs.order_by('-is_active', 'subcategory', 'inventory_number')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['computers_count'] = Equipment.objects.filter(
            subcategory__slug='desktop', archived=False).count()
        context['laptops_count'] = Equipment.objects.filter(
            subcategory__slug='laptop', archived=False).count()
        context['tablets_count'] = Equipment.objects.filter(
            subcategory__slug='tablet', archived=False).count()
        context['monitors_count'] = Equipment.objects.filter(
            subcategory__slug='monitor', archived=False).count()
        context['servers_count'] = Equipment.objects.filter(
            subcategory__slug='server', archived=False).count()
        context['printers_count'] = Equipment.objects.filter(
            category__slug='printers_top', archived=False).count()
        context['medical_count'] = Equipment.objects.filter(
            category__slug='medical_top', archived=False).count()
        context['peripherals_count'] = Equipment.objects.filter(
            category__slug='periphery_top', archived=False).count()
        context['phones_count'] = Equipment.objects.filter(
            subcategory__slug__in=['voip_phone', 'system_phone', 'cordless_phone', 'cellular_phone'],
            archived=False).count()
        context['vks_count'] = Equipment.objects.filter(
            subcategory__slug='vks', archived=False).count()
        return context


# ============================================================================
# Список техники
# ============================================================================

@login_required
def equipment_list(request):
    """Общий список всего оборудования."""
    equipment_qs = Equipment.objects.filter(archived=False).select_related(
        'assigned_user', 'responsible_user', 'category', 'subcategory'
    )

    # Фильтры
    category_slug = request.GET.get('category')
    subcategory_slug = request.GET.get('subcategory')
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status')
    location = request.GET.get('location', '').strip()
    assigned_dept = request.GET.get('assigned_dept', '').strip()
    responsible_dept = request.GET.get('responsible_dept', '').strip()
    assigned_user = request.GET.get('assigned_user', '').strip()
    responsible_user = request.GET.get('responsible_user', '').strip()

    if category_slug:
        cat = EquipmentCategory.objects.filter(slug=category_slug, is_active=True).first()
        if cat and cat.is_top_level:
            equipment_qs = equipment_qs.filter(category=cat)
    if subcategory_slug:
        subcat = EquipmentCategory.objects.filter(slug=subcategory_slug, is_active=True).first()
        if subcat and not subcat.is_top_level:
            equipment_qs = equipment_qs.filter(subcategory=subcat)
    if search:
        equipment_qs = equipment_qs.filter(
            Q(inventory_number__icontains=search)
            | Q(serial_number__icontains=search)
            | Q(name__icontains=search)
            | Q(brand__name__icontains=search)
            | Q(model__icontains=search)
            | Q(hostname__icontains=search)
            | Q(ip_address__icontains=search)
            | Q(location__icontains=search)
        )
    if status:
        equipment_qs = equipment_qs.filter(status=status)
    if location:
        equipment_qs = equipment_qs.filter(location__icontains=location)

    # Фильтр по подразделению закрепленного сотрудника
    if assigned_dept:
        from accounts.models import Department as AccountDepartment
        dept = AccountDepartment.objects.filter(name=assigned_dept).first()
        if dept:
            equipment_qs = equipment_qs.filter(assigned_user__department=dept)
        else:
            equipment_qs = equipment_qs.none()

    # Фильтр по подразделению МОЛ
    if responsible_dept:
        from accounts.models import Department as AccountDepartment
        dept = AccountDepartment.objects.filter(name=responsible_dept).first()
        if dept:
            equipment_qs = equipment_qs.filter(responsible_user__department=dept)
        else:
            equipment_qs = equipment_qs.none()

    # Фильтр по ФИО закрепленного сотрудника
    if assigned_user:
        parts = assigned_user.split()
        if len(parts) >= 2:
            last_name = parts[0]
            first_name = parts[1]
            equipment_qs = equipment_qs.filter(
                Q(assigned_user__last_name__icontains=last_name)
                & Q(assigned_user__first_name__icontains=first_name)
            )
        elif len(parts) == 1:
            equipment_qs = equipment_qs.filter(
                Q(assigned_user__last_name__icontains=parts[0])
                | Q(assigned_user__first_name__icontains=parts[0])
                | Q(assigned_user__patronymic__icontains=parts[0])
            )

    # Фильтр по ФИО МОЛ
    if responsible_user:
        parts = responsible_user.split()
        if len(parts) >= 2:
            last_name = parts[0]
            first_name = parts[1]
            equipment_qs = equipment_qs.filter(
                Q(responsible_user__last_name__icontains=last_name)
                & Q(responsible_user__first_name__icontains=first_name)
            )
        elif len(parts) == 1:
            equipment_qs = equipment_qs.filter(
                Q(responsible_user__last_name__icontains=parts[0])
                | Q(responsible_user__first_name__icontains=parts[0])
                | Q(responsible_user__patronymic__icontains=parts[0])
            )

    # Сортировка
    allowed_sort_fields = {
        'inventory_number': ['inventory_number', '-inventory_number'],
        'name': ['name', '-name'],
        'category': ['category__name', '-category__name'],
        'assigned_user': ['assigned_user__last_name', '-assigned_user__last_name'],
        'responsible_user': ['responsible_user__last_name', '-responsible_user__last_name'],
        'status': ['status', '-status'],
    }
    sort_field = request.GET.get('sort', '')
    sort_order = request.GET.get('order', '')

    if sort_field in allowed_sort_fields:
        if sort_order == 'desc':
            equipment_qs = equipment_qs.order_by(*reversed(allowed_sort_fields[sort_field]))
        else:
            equipment_qs = equipment_qs.order_by(*allowed_sort_fields[sort_field])
    else:
        equipment_qs = equipment_qs.order_by('-is_active', 'category', 'subcategory', 'inventory_number')

    equipment_qs = equipment_qs.select_related(
        'assigned_user', 'responsible_user', 'category', 'subcategory',
        'subcategory__parent',
    )

    total_count = equipment_qs.count()

    # Pagination
    page_number = request.GET.get('page', 1)
    items_per_page = request.GET.get('per_page', 50)

    # Validate items_per_page
    valid_page_sizes = [20, 50, 100, 200]
    if str(items_per_page) not in [str(s) for s in valid_page_sizes]:
        items_per_page = 50
    else:
        items_per_page = int(items_per_page)

    paginator = Paginator(equipment_qs, items_per_page)
    page_obj = paginator.get_page(page_number)

    # Top-level categories for filter
    top_categories = EquipmentCategory.objects.filter(
        parent__isnull=True, is_active=True
    ).order_by('name')

    # Top-level categories for filter dropdown
    categories = list(
        EquipmentCategory.objects.filter(parent__isnull=True, is_active=True)
        .order_by('name')
        .values_list('slug', 'name')
    )

    # All subcategories for filter dropdown
    subtypes = list(
        EquipmentCategory.objects.filter(is_active=True)
        .order_by('parent__name', 'name')
        .values_list('slug', 'name')
    )

    # Departments for filter dropdowns
    from accounts.models import Department as AccountDepartment, User as AccountUser
    departments = list(
        AccountDepartment.objects.filter(is_active=True)
        .order_by('name')
        .values_list('name', flat=True)
    )

    # Users for filter dropdowns (only those with equipment assigned)
    assigned_users = list(
        AccountUser.objects.filter(equipment_assigned__archived=False).distinct()
        .order_by('last_name', 'first_name')
        .values_list('id', 'last_name')
    )
    responsible_users = list(
        AccountUser.objects.filter(equipment_responsible__archived=False).distinct()
        .order_by('last_name', 'first_name')
        .values_list('id', 'last_name')
    )
    # Combine and deduplicate users
    all_users_map = {}
    for uid, uname in assigned_users + responsible_users:
        if uid not in all_users_map:
            all_users_map[uid] = uname
    all_users = [(uid, uname) for uid, uname in all_users_map.items()]

    # Counts for sidebar badges
    computers_count = Equipment.objects.filter(
        subcategory__slug='desktop', archived=False
    ).count()
    laptops_count = Equipment.objects.filter(
        subcategory__slug='laptop', archived=False
    ).count()
    tablets_count = Equipment.objects.filter(
        subcategory__slug='tablet', archived=False
    ).count()
    monitors_count = Equipment.objects.filter(
        subcategory__slug='monitor', archived=False
    ).count()
    servers_count = Equipment.objects.filter(
        subcategory__slug='server', archived=False
    ).count()
    printers_count = Equipment.objects.filter(
        category__slug='printers_top', archived=False
    ).count()
    medical_count = Equipment.objects.filter(
        category__slug='medical_top', archived=False
    ).count()
    peripherals_count = Equipment.objects.filter(
        category__slug='periphery_top', archived=False
    ).count()
    phones_count = Equipment.objects.filter(
        subcategory__slug__in=['voip_phone', 'system_phone', 'cordless_phone', 'cellular_phone'],
        archived=False
    ).count()
    vks_count = Equipment.objects.filter(
        subcategory__slug='vks', archived=False
    ).count()

    context = {
        'equipment_list': page_obj,
        'total_count': total_count,
        'page_obj': page_obj,
        'current_per_page': items_per_page,
        'valid_page_sizes': valid_page_sizes,
        'status_choices': EQUIPMENT_STATUS_CHOICES,
        'categories': categories,
        'subtypes': subtypes,
        'top_categories': top_categories,
        'departments': departments,
        'all_users': all_users,
        'current_category': category_slug,
        'current_subcategory': subcategory_slug,
        'current_search': search,
        'current_status': status,
        'current_location': location,
        'current_assigned_dept': assigned_dept,
        'current_responsible_dept': responsible_dept,
        'current_assigned_user': assigned_user,
        'current_responsible_user': responsible_user,
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
        # Сортировка
        'current_sort': sort_field,
        'current_order': sort_order,
        # Filters для сохранения в сортировке
        'filters': request.GET.copy,
    }
    return render(request, 'equipment/equipment_list.html', context)


# ============================================================================
# Справочник категорий
# ============================================================================

@login_required
def categories_reference(request):
    """Справочник категорий и подкатегорий оборудования (иерархический)."""
    # Статистика по категориям (иерархия)
    top_categories = EquipmentCategory.objects.filter(
        parent__isnull=True, is_active=True
    ).prefetch_related('children').order_by('name')

    category_stats = {}
    for top_cat in top_categories:
        count = Equipment.objects.filter(category=top_cat, archived=False).count()
        subcategories = top_cat.children.filter(is_active=True)
        subcategory_counts = {}
        for subcat in subcategories:
            subtype_count = Equipment.objects.filter(
                subcategory=subcat, archived=False
            ).count()
            subcategory_counts[subcat.name] = subtype_count
        category_stats[top_cat.name] = {
            'pk': top_cat.pk,
            'slug': top_cat.slug,
            'count': count,
            'subcategories': subcategory_counts,
        }

    # Статистика по статусам
    status_stats = {}
    for status_value, status_label in [('active', 'Активно'), ('maintenance', 'На обслуживании'), ('decommissioned', 'Списано')]:
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
        'computers_count': Equipment.objects.filter(subcategory__slug='desktop', archived=False).count(),
        'laptops_count': Equipment.objects.filter(subcategory__slug='laptop', archived=False).count(),
        'tablets_count': Equipment.objects.filter(subcategory__slug='tablet', archived=False).count(),
        'monitors_count': Equipment.objects.filter(subcategory__slug='monitor', archived=False).count(),
        'servers_count': Equipment.objects.filter(subcategory__slug='server', archived=False).count(),
        'printers_count': Equipment.objects.filter(category__slug='printers_top', archived=False).count(),
        'medical_count': Equipment.objects.filter(category__slug='medical_top', archived=False).count(),
        'peripherals_count': Equipment.objects.filter(category__slug='periphery_top', archived=False).count(),
        'phones_count': Equipment.objects.filter(subcategory__slug__in=['voip_phone', 'system_phone', 'cordless_phone', 'cellular_phone'], archived=False).count(),
        'vks_count': Equipment.objects.filter(subcategory__slug='vks', archived=False).count(),
    }
    return render(request, 'equipment/categories_reference.html', context)


# ============================================================================
# Стубы для существующих URL (предыдущая реализация отсутствует в views.py)
# ============================================================================

def _sidebar_counts():
    """Возвращает словарь счётчиков для бейджей в сайдбаре."""
    return {
        'computers_count': Equipment.objects.filter(
            subcategory__slug='desktop', archived=False).count(),
        'laptops_count': Equipment.objects.filter(
            subcategory__slug='laptop', archived=False).count(),
        'tablets_count': Equipment.objects.filter(
            subcategory__slug='tablet', archived=False).count(),
        'monitors_count': Equipment.objects.filter(
            subcategory__slug='monitor', archived=False).count(),
        'servers_count': Equipment.objects.filter(
            subcategory__slug='server', archived=False).count(),
        'printers_count': Equipment.objects.filter(
            category__slug='printers_top', archived=False).count(),
        'medical_count': Equipment.objects.filter(
            category__slug='medical_top', archived=False).count(),
        'peripherals_count': Equipment.objects.filter(
            category__slug='periphery_top', archived=False).count(),
        'phones_count': Equipment.objects.filter(
            subcategory__slug__in=['voip_phone', 'system_phone', 'cordless_phone', 'cellular_phone'],
            archived=False).count(),
        'vks_count': Equipment.objects.filter(
            subcategory__slug='vks', archived=False).count(),
        # Категории первого уровня с количеством оборудования
        'top_categories': EquipmentCategory.objects.filter(
            parent__isnull=True, is_active=True
        ).exclude(slug='').prefetch_related().annotate(
            eq_count=Count(
                'equipment_items',
                filter=Q(equipment_items__archived=False),
                distinct=True,
            )
        ).order_by('name'),
    }

def export_equipment_to_excel(request):
    """Стуб: экспорт оборудования в Excel."""
    return render(request, 'equipment/equipment_list.html', {**_sidebar_counts(), 'equipment_list': Equipment.objects.none()})

@login_required
def dashboard(request):
    """Дашборд: сводная информация по категориям, статусам и подразделениям."""
    equipment_qs = Equipment.objects.filter(archived=False).select_related(
        'assigned_user', 'assigned_user__department', 'responsible_user', 'responsible_user__department',
        'category', 'subcategory',
    )

    # === Сводка по категориям ===
    category_stats = []
    top_categories = EquipmentCategory.objects.filter(parent__isnull=True, is_active=True).order_by('name')
    for cat in top_categories:
        count = equipment_qs.filter(category=cat).count()
        subcats = cat.children.filter(is_active=True)
        subcat_data = []
        for sc in subcats:
            sub_count = equipment_qs.filter(subcategory=sc).count()
            if sub_count > 0:
                subcat_data.append({'name': sc.name, 'count': sub_count})
        category_stats.append({
            'name': cat.name,
            'slug': cat.slug,
            'count': count,
            'subcategories': subcat_data,
        })

    # === Сводка по статусам ===
    status_stats = []
    for status_value, status_label in EQUIPMENT_STATUS_CHOICES:
        count = equipment_qs.filter(status=status_value).count()
        if count > 0:
            status_stats.append({'value': status_value, 'label': status_label, 'count': count})

    # === Таблица 1: По подразделению закрепленного за техникой сотрудника (assigned_user) ===
    assigned_dept_data = {}
    assigned_qs = equipment_qs.exclude(assigned_user__isnull=True)
    for item in assigned_qs:
        dept = item.assigned_user.department
        if not dept:
            continue
        dept_name = dept.name
        cat_name = item.category.name if item.category else 'Без категории'
        if dept_name not in assigned_dept_data:
            assigned_dept_data[dept_name] = {'total': 0, 'categories': {}}
        assigned_dept_data[dept_name]['total'] += 1
        if cat_name not in assigned_dept_data[dept_name]['categories']:
            assigned_dept_data[dept_name]['categories'][cat_name] = 0
        assigned_dept_data[dept_name]['categories'][cat_name] += 1

    # Sort by total descending
    assigned_depts = sorted(assigned_dept_data.items(), key=lambda x: x[1]['total'], reverse=True)

    # === Таблица 2: По подразделению МОЛ (responsible_user) ===
    mol_dept_data = {}
    mol_qs = equipment_qs.exclude(responsible_user__isnull=True)
    for item in mol_qs:
        dept = item.responsible_user.department
        if not dept:
            continue
        dept_name = dept.name
        cat_name = item.category.name if item.category else 'Без категории'
        if dept_name not in mol_dept_data:
            mol_dept_data[dept_name] = {'total': 0, 'categories': {}}
        mol_dept_data[dept_name]['total'] += 1
        if cat_name not in mol_dept_data[dept_name]['categories']:
            mol_dept_data[dept_name]['categories'][cat_name] = 0
        mol_dept_data[dept_name]['categories'][cat_name] += 1

    mol_depts = sorted(mol_dept_data.items(), key=lambda x: x[1]['total'], reverse=True)

    # === Подкатегории "Компьютерное оборудование" ===
    computer_cat = EquipmentCategory.objects.filter(slug='computer_top', is_active=True).first()
    computer_subcats = []
    computer_subcat_names = []
    if computer_cat:
        computer_subcats = list(computer_cat.children.filter(is_active=True).order_by('name'))
        computer_subcat_names = [sc.name for sc in computer_subcats]

    # === Таблица 3: По подразделению assigned_user — подкатегории компьютерного оборудования ===
    assigned_comp_data = {}
    for item in equipment_qs.filter(subcategory__in=computer_subcats).exclude(assigned_user__isnull=True):
        dept = item.assigned_user.department
        if not dept:
            continue
        dept_name = dept.name
        subcat_name = item.subcategory.name if item.subcategory else 'Без подкатегории'
        if dept_name not in assigned_comp_data:
            assigned_comp_data[dept_name] = {'total': 0, 'subcategories': {}}
        assigned_comp_data[dept_name]['total'] += 1
        if subcat_name not in assigned_comp_data[dept_name]['subcategories']:
            assigned_comp_data[dept_name]['subcategories'][subcat_name] = 0
        assigned_comp_data[dept_name]['subcategories'][subcat_name] += 1

    assigned_comp_depts = sorted(assigned_comp_data.items(), key=lambda x: x[1]['total'], reverse=True)

    # === Таблица 4: По подразделению МОЛ — подкатегории компьютерного оборудования ===
    mol_comp_data = {}
    for item in equipment_qs.filter(subcategory__in=computer_subcats).exclude(responsible_user__isnull=True):
        dept = item.responsible_user.department
        if not dept:
            continue
        dept_name = dept.name
        subcat_name = item.subcategory.name if item.subcategory else 'Без подкатегории'
        if dept_name not in mol_comp_data:
            mol_comp_data[dept_name] = {'total': 0, 'subcategories': {}}
        mol_comp_data[dept_name]['total'] += 1
        if subcat_name not in mol_comp_data[dept_name]['subcategories']:
            mol_comp_data[dept_name]['subcategories'][subcat_name] = 0
        mol_comp_data[dept_name]['subcategories'][subcat_name] += 1

    mol_comp_depts = sorted(mol_comp_data.items(), key=lambda x: x[1]['total'], reverse=True)

    # === Количество сотрудников по подразделениям (из accounts) ===
    from accounts.models import User as AccountUser
    dept_user_counts = {}
    for dept in Department.objects.filter(is_active=True):
        count = AccountUser.objects.filter(department=dept).count()
        if count > 0:
            dept_user_counts[dept.name] = count

    context = {
        **_sidebar_counts(),
        'category_stats': category_stats,
        'status_stats': status_stats,
        'assigned_depts': assigned_depts,
        'mol_depts': mol_depts,
        'all_categories': [item['name'] for item in category_stats],
        # Computer subcategories
        'computer_subcat_names': computer_subcat_names,
        'assigned_comp_depts': assigned_comp_depts,
        'mol_comp_depts': mol_comp_depts,
        'dept_user_counts': dept_user_counts,
    }
    return render(request, 'equipment/dashboard.html', context)

def department_equipment(request, department_id):
    """Стуб: оборудование подразделения."""
    return render(request, 'equipment/department_equipment.html', _sidebar_counts())

@login_required
def download_new_items(request):
    """Скачивание CSV файла с новыми позициями."""
    # Get new items from session (set during upload)
    new_items = request.session.get('upload_new_items', [])
    if not new_items:
        messages.error(request, 'Нет новых позиций для скачивания')
        return redirect('equipment:upload_os')

    # Create CSV response
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="new_os_items.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Наименование', 'МОЛ/Место хранения', 'Инвентарный номер',
                     'Заводской номер', 'Тип НФА'])

    for item in new_items:
        writer.writerow([
            item.get('name', ''),
            item.get('mol', ''),
            item.get('inventory', ''),
            item.get('serial', ''),
            item.get('nfa_type', ''),
        ])

    return response


@login_required
def _import_single_item(item):
    """
    Импортирует одну позицию в базу данных Equipment.
    
    Возвращает словарь с результатами:
        {'created': bool, 'skipped_no_inventory': bool, 'skipped_duplicate': bool,
         'error': str|None}
    
    Выбрасывает исключения, которые перехватываются на уровне цикла
    в import_new_items_to_db — это позволяет продолжить импорт остальных позиций.
    """
    name = item.get('name', '').strip()
    inventory = item.get('inventory', '').strip()
    serial = item.get('serial', '').strip()
    mol = item.get('mol', '').strip()
    categories = item.get('categories', [])
    
    result = {
        'created': False,
        'skipped_no_inventory': False,
        'skipped_duplicate': False,
        'error': None,
    }
    
    # Пропускаем позиции без корректного инвентарного номера
    if not inventory or inventory in ('<групповой учет>', '<не задан>', ''):
        result['skipped_no_inventory'] = True
        return result
    
    # Проверяем дубликат
    if Equipment.objects.filter(inventory_number=inventory).exists():
        result['skipped_duplicate'] = True
        return result
    
    # Определяем категорию
    category = None
    subcategory = None
    if categories:
        # Берём первую категорию
        cat_name = categories[0]
        # Ищем категорию по name или slug
        category = EquipmentCategory.objects.filter(
            Q(name__icontains=cat_name) | Q(slug__icontains=cat_name),
            is_active=True
        ).first()
        
        # Если не нашли, создаём
        if not category:
            category = EquipmentCategory.objects.create(
                name=cat_name,
                is_active=True
            )
    
    # Ищем МОЛ (материально ответственное лицо)
    responsible_user = None
    if mol and mol not in ('<групповой учет>', '<не задан>', ''):
        mio_result = _parse_and_find_mol(mol)
        if mio_result['found']:
            responsible_user = mio_result['user']
    
    # Создаём оборудование
    Equipment.objects.create(
        inventory_number=inventory,
        serial_number=serial if serial else None,
        name=name,
        category=category,
        subcategory=subcategory,
        responsible_user=responsible_user,
        status='confirmed',
        is_active=True,
        archived=False,
    )
    result['created'] = True
    return result


def import_new_items_to_db(request):
    """Импорт новых позиций из сессии в базу данных Equipment.
    
    Загружаются только позиции с корректным инвентарным номером.
    Позиции без инв. номера (<не задан>, <групповой учет>, пустые) пропускаются.
    """
    new_items = request.session.get('upload_new_items', [])
    
    if not new_items:
        messages.warning(request, 'Нет позиций для импорта. Сначала загрузите CSV файл.')
        return redirect('equipment:upload_os')
    
    created_count = 0
    skipped_no_inventory = 0
    skipped_duplicate = 0
    errors = []
    
    for item in new_items:
        try:
            result = _import_single_item(item)
            if result['created']:
                created_count += 1
            elif result['skipped_no_inventory']:
                skipped_no_inventory += 1
            elif result['skipped_duplicate']:
                skipped_duplicate += 1
        except Exception as exc:
            logger.exception(f'Ошибка импорта позиции: {exc}')
            errors.append(f'Ошибка обработки позиции: {str(exc)}')
    
    # Очищаем сессию
    if 'upload_new_items' in request.session:
        del request.session['upload_new_items']
    
    # Формируем сообщение
    msg = f'Импорт завершён: создано {created_count}'
    if skipped_no_inventory:
        msg += f', пропущено без инв. номера: {skipped_no_inventory}'
    if skipped_duplicate:
        msg += f', пропущено (дубликат): {skipped_duplicate}'
    if errors:
        msg += f'. Ошибки: {"; ".join(errors[:5])}'
    
    if created_count > 0:
        messages.success(request, msg)
    else:
        messages.warning(request, msg)
    
    return redirect('equipment:upload_os')


def _process_csv_row(row, row_num, clean_field, processed_inventory_numbers,
                     csv_duplicate_inventory, csv_duplicate_serial, csv_serial_in_db,
                     stats):
    """
    Обрабатывает одну строку CSV-файла основных средств.
    
    Все исключения перехватываются на уровне цикла — эта функция может
    выбрасывать исключения, которые будут записаны в stats['errors']
    без прерывания загрузки остальных строк.
    """
    inventory_number = clean_field(row.get('Инвентарный номер', ''))
    mol_field = clean_field(row.get('МОЛ/Место хранения', ''))
    name = clean_field(row.get('Наименование', ''))
    serial_number = clean_field(row.get('Заводской номер', ''))
    # Очищаем префикс SN если есть
    if serial_number and serial_number.upper().startswith('SN'):
        serial_number = serial_number[2:]
    nfa_type = clean_field(row.get('Тип НФА', ''))

    # Debug: log specific inventory numbers
    if '2143230100000001' in inventory_number or '2143230100000001' in row.get('Инвентарный номер', ''):
        logger.warning(f'DEBUG row {row_num}: inv="{inventory_number}" raw="{row.get("Инвентарный номер", "")}" name="{name}" serial="{serial_number}"')

    # Skip rows with group accounting or no inventory
    if inventory_number in ('<групповой учет>', '<не задан>', ''):
        if inventory_number in ('<групповой учет>', '<не задан>'):
            stats['group_accounting'] += 1
        else:
            stats['no_inventory'] += 1

        # Filter by name
        categories = classify_by_name(name)
        item_data = {
            'name': name,
            'mol': mol_field,
            'inventory': inventory_number,
            'serial': serial_number,
            'nfa_type': nfa_type,
            'row_num': row_num,
            'categories': categories,
        }
        
        if categories:
            stats['new_items_filtered'].append(item_data)
            for cat in categories:
                stats['category_stats'][cat] = stats['category_stats'].get(cat, 0) + 1
        else:
            stats['new_items_excluded'].append(item_data)
        return

    stats['valid_inventory_rows'] += 1

    # Check for duplicates in this file (inventory number)
    if inventory_number in processed_inventory_numbers:
        csv_duplicate_inventory.append({
            'row_num': row_num,
            'inventory': inventory_number,
            'name': name,
        })
        return
    processed_inventory_numbers.add(inventory_number)

    # Check for duplicate serial number in this file
    if serial_number:
        if serial_number in csv_serial_in_db:
            csv_duplicate_serial.append({
                'row_num': row_num,
                'serial': serial_number,
                'name': name,
            })
            return
        csv_serial_in_db.add(serial_number)

    # Try to find equipment by inventory number (with normalization)
    equipment = _find_equipment_by_inventory(inventory_number)
    
    # Debug: log specific inventory numbers
    if '2143230100000001' == inventory_number:
        logger.warning(f'DEBUG search: inv="{inventory_number}" found={equipment is not None}')
        if equipment:
            logger.warning(f'DEBUG found: {equipment.name}, status={equipment.status}')

    if equipment:
        stats['found_by_inventory'] += 1
        equipment.status = 'confirmed'
        
        # Debug: log specific inventory numbers
        if '2143230100000001' == inventory_number:
            logger.warning(f'DEBUG confirmed: {inventory_number} -> {equipment.name}')

        # Parse MIO and assign responsible_user
        if mol_field and mol_field not in ('<групповой учет>', '<не задан>'):
            mio_result = _parse_and_find_mol(mol_field)
            if mio_result['found']:
                equipment.responsible_user = mio_result['user']
                stats['mio_stats']['found'] += 1
            else:
                stats['mio_stats']['not_found'] += 1
                stats['mio_failures'].append({
                    'row_num': row_num,
                    'inventory': inventory_number,
                    'name': name,
                    'mol': mol_field,
                    'reason': mio_result['reason'],
                    'match_info': mio_result['match_info'],
                })

        # Update serial number if provided and empty
        if serial_number and not equipment.serial_number:
            equipment.serial_number = serial_number

        try:
            equipment.save(update_fields=['status', 'responsible_user', 'serial_number'])
            stats['confirmed'] += 1
        except Exception as e:
            # Если конфликт уникальности — обновляем без serial_number
            if 'serial_number_unique' in str(e):
                equipment.serial_number = None  # Отменяем обновление сер. номера
                equipment.status = 'confirmed'
                if mol_field and mol_field not in ('<групповой учет>', '<не задан>'):
                    equipment.responsible_user = mio_result['user'] if mio_result.get('found') else equipment.responsible_user
                try:
                    equipment.save(update_fields=['status', 'responsible_user'])
                    stats['confirmed'] += 1
                    stats['csv_serial_conflict'].append({
                        'row_num': row_num,
                        'inventory': inventory_number,
                        'serial': serial_number,
                        'name': name,
                    })
                except:
                    pass
            else:
                raise
    else:
        stats['not_found_by_inventory'] += 1

        # Try to find by serial number
        if serial_number:
            eq_by_serial = Equipment.objects.filter(
                serial_number=serial_number, archived=False
            ).first()
            if eq_by_serial:
                equipment = eq_by_serial
                stats['found_by_serial'] += 1
                equipment.status = 'confirmed'

                if mol_field and mol_field not in ('<групповой учет>', '<не задан>'):
                    mio_result = _parse_and_find_mol(mol_field)
                    if mio_result['found']:
                        equipment.responsible_user = mio_result['user']
                        stats['mio_stats']['found'] += 1
                    else:
                        stats['mio_stats']['not_found'] += 1
                        stats['mio_failures'].append({
                            'row_num': row_num,
                            'inventory': inventory_number,
                            'name': name,
                            'mol': mol_field,
                            'reason': mio_result['reason'],
                            'match_info': mio_result['match_info'],
                        })

                equipment.save(update_fields=['status', 'responsible_user'])
                stats['confirmed_by_serial'] += 1
            else:
                stats['not_found_by_serial'] += 1
                
                # Check if serial number already exists in DB
                if serial_number:
                    existing_by_serial = Equipment.objects.filter(
                        serial_number=serial_number, archived=False
                    ).exclude(inventory_number=inventory_number).first()
                    if existing_by_serial:
                        stats['csv_serial_conflict'].append({
                            'row_num': row_num,
                            'inventory': inventory_number,
                            'serial': serial_number,
                            'name': name,
                            'conflict_with': existing_by_serial.inventory_number,
                        })
                categories = classify_by_name(name)
                item_data = {
                    'name': name,
                    'mol': mol_field,
                    'inventory': inventory_number,
                    'serial': serial_number,
                    'nfa_type': nfa_type,
                    'row_num': row_num,
                    'categories': categories,
                }
                
                if categories:
                    stats['new_items_filtered'].append(item_data)
                    for cat in categories:
                        stats['category_stats'][cat] = stats['category_stats'].get(cat, 0) + 1
                else:
                    stats['new_items_excluded'].append(item_data)
        else:
            stats['not_found_by_serial'] += 1
            categories = classify_by_name(name)
            item_data = {
                'name': name,
                'mol': mol_field,
                'inventory': inventory_number,
                'serial': serial_number,
                'nfa_type': nfa_type,
                'row_num': row_num,
                'categories': categories,
            }
            
            if categories:
                stats['new_items_filtered'].append(item_data)
                for cat in categories:
                    stats['category_stats'][cat] = stats['category_stats'].get(cat, 0) + 1
            else:
                stats['new_items_excluded'].append(item_data)


def upload_os_csv(request):
    """Загрузка и обработка CSV файла основных средств."""

    stats = {
                'total_rows': 0,
                'valid_inventory_rows': 0,
                'found_by_inventory': 0,
                'confirmed': 0,
                'not_found_by_inventory': 0,
                'found_by_serial': 0,
                'confirmed_by_serial': 0,
                'not_found_by_serial': 0,
                'group_accounting': 0,
                'no_inventory': 0,
                'new_items': [],
                'new_items_filtered': [],  # Только позиции, попадающие под фильтр
                'new_items_excluded': [],  # Позиции, исключённые фильтром
                'category_stats': {},  # Статистика по категориям новых позиций
                'filter_keywords': _get_filter_keywords(),  # Для отображения пользователю
                'exclude_keywords': _get_exclude_keywords(),  # Исключения для отображения
                'mio_failures': [],  # Ошибки поиска МОЛ
                'mio_stats': {
                    'total_mol': 0,
                    'found': 0,
                    'not_found': 0,
                    'too_many': 0,
                    'no_name': 0,
                },
                'errors': [],
                'csv_duplicate_inventory': [],  # Дубликаты инв. номеров в CSV
                'csv_duplicate_serial': [],  # Дубликаты сер. номеров в CSV
                'csv_serial_conflict': [],  # Конфликт сер. номеров с БД
            }

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'Выберите файл для загрузки')
            return render(request, 'equipment/upload_os_csv.html', {
                **_sidebar_counts(),
                'stats': None,
                'error': 'Файл не выбран',
            })

        try:
            # Decode file content
            file_content = csv_file.read().decode('utf-8-sig')
            
            # Detect delimiter (semicolon or comma)
            delimiter = ';' if ';' in file_content.split('\n')[0] else ','
            reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)

            # Track inventory numbers we've seen (for dedup)
            processed_inventory_numbers = set()
            csv_duplicate_inventory = []  # Дубликаты инв. номеров в CSV
            csv_duplicate_serial = []  # Дубликаты сер. номеров в CSV
            csv_serial_in_db = set()  # Серийные номера из CSV для проверки дубликатов

            # Helper function for cleaning fields
            def clean_field(value):
                """Очищаем поле от невидимых Unicode символов."""
                if not value:
                    return ''
                value = value.replace('\u00a0', ' ').replace('\u200b', '').replace('\ufeff', '')
                value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
                return value.strip()

            for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
                try:
                    _process_csv_row(
                        row, row_num, clean_field, processed_inventory_numbers,
                        csv_duplicate_inventory, csv_duplicate_serial, csv_serial_in_db,
                        stats,
                    )
                except Exception as exc:
                    # Обработка отдельной строки: ошибка не прерывает загрузку
                    logger.exception(f'Ошибка обработки строки {row_num}: {exc}')
                    stats['errors'].append({
                        'row_num': row_num,
                        'error': str(exc),
                        'raw': {k: row.get(k, '') for k in row},
                    })

            messages.success(request, 'Файл основных средств успешно обработан')

            # Add warnings for duplicates
            if csv_duplicate_inventory:
                messages.warning(request, f'Пропущено {len(csv_duplicate_inventory)} строк с дублирующимся инвентарным номером в файле')
            if csv_duplicate_serial:
                messages.warning(request, f'Пропущено {len(csv_duplicate_serial)} строк с дублирующимся серийным номером в файле')
            if stats['csv_serial_conflict']:
                messages.warning(request, f'Пропущено {len(stats["csv_serial_conflict"])} позиций — конфликт серийного номера с существующим оборудованием в базе')

            # Save filtered new items to session for download
            request.session['upload_new_items'] = stats['new_items_filtered']

        except Exception as e:
            logger.exception('Ошибка обработки CSV файла')
            stats['errors'].append(str(e))
            messages.error(request, f'Ошибка обработки файла: {e}')

        return render(request, 'equipment/upload_os_csv.html', {
            **_sidebar_counts(),
            'stats': stats,
        })

    return render(request, 'equipment/upload_os_csv.html', {
        **_sidebar_counts(),
        'stats': None,
    })


def _parse_and_find_mol(mol_field):
    """
    Парсит поле МОЛ и ищет пользователя в базе.
    Формат: 'Фамилия И. О. - Подразделение' или 'Фамилия Имя Отчество - Подразделение'
    
    Примеры:
      'Краснобаева Ю. С. - Отдел экспериментальной и клинической кардиологии'
      'Лузанов А. К. - Отдел информационных технологий'
      'Иванов Иван Иванович - Отдел'
    
    Возвращает словарь:
    {
        'found': True/False,
        'user': User/None,
        'reason': str - причина неудачи или 'success',
        'match_info': dict - информация о поиске,
    }
    """
    from accounts.models import User, Department
    
    result = {
        'found': False,
        'user': None,
        'reason': '',
        'match_info': {},
    }
    
    if not mol_field or mol_field in ('<групповой учет>', '<не задан>'):
        result['reason'] = 'group_accounting'
        result['match_info'] = {'mol': mol_field}
        return result

    # Split by ' - ' to get name and department
    parts = mol_field.split(' - ')
    if len(parts) < 1:
        result['reason'] = 'no_separator'
        result['match_info'] = {'mol': mol_field}
        return result

    name_part = parts[0].strip()
    dept_name = parts[1].strip() if len(parts) > 1 else ''

    # Parse name: "Фамилия И. О." or "Фамилия Имя Отчество"
    name_parts = name_part.split()
    if len(name_parts) < 2:
        result['reason'] = 'incomplete_name'
        result['match_info'] = {'mol': mol_field, 'name_part': name_part}
        return result

    last_name = name_parts[0]
    first_name_raw = name_parts[1] if len(name_parts) > 1 else ''
    patronymic_raw = name_parts[2] if len(name_parts) > 2 else ''

    # Detect format: initials (single letter with/without dots) or full names
    is_initials = (
        len(first_name_raw.replace('.', '')) == 1 and
        len(patronymic_raw.replace('.', '')) == 1
    )

    # Clean up: remove dots, strip whitespace, lowercase for comparison
    first_name_clean = first_name_raw.replace('.', '').strip().lower()
    patronymic_clean = patronymic_raw.replace('.', '').strip().lower()

    result['match_info'] = {
        'last_name': last_name,
        'first_name_raw': first_name_raw,
        'patronymic_raw': patronymic_raw,
        'is_initials': is_initials,
        'department': dept_name,
    }

    # Helper: try to find user with given filters
    def try_find_user(filters, query_desc):
        """Try to find user, return (found, user, match_info)."""
        try:
            users = User.objects.filter(**filters)
            count = users.count()
            match_info = dict(result['match_info'])
            match_info['query'] = query_desc
            match_info['matches'] = count

            if count == 1:
                return True, users.first(), match_info
            elif count > 1:
                match_info['users'] = [
                    {'id': u.id, 'name': u.get_full_name(), 'department': u.department.name if u.department else None}
                    for u in users[:5]
                ]
                match_info['total_matches'] = count
                return False, None, match_info
        except Exception:
            pass
        return False, None, match_info

    # Strategy 1: ФИО + подразделение (если инициалы — используем startswith)
    if dept_name:
        try:
            dept = Department.objects.filter(
                name__icontains=dept_name
            ).first()
            if dept:
                result['match_info']['department_found'] = dept.name
                
                if is_initials:
                    # Инициалы: Фамилия + первая буква имени + первая буква отчества
                    q = {
                        'last_name__iexact': last_name,
                        'first_name__istartswith': first_name_clean,
                        'patronymic__istartswith': patronymic_clean,
                        'department': dept,
                    }
                    found, user, mi = try_find_user(q, f"Ф={last_name}, И={first_name_clean}*, О={patronymic_clean}*, Под={dept.name}")
                    if found:
                        result['found'] = True
                        result['user'] = user
                        result['reason'] = 'success'
                        result['match_info'] = mi
                        return result
                else:
                    # Полные ФИО
                    q = {
                        'last_name__iexact': last_name,
                        'first_name__iexact': first_name_clean,
                        'patronymic__iexact': patronymic_clean,
                        'department': dept,
                    }
                    found, user, mi = try_find_user(q, f"ФИО={last_name} {first_name_clean} {patronymic_clean}, Под={dept.name}")
                    if found:
                        result['found'] = True
                        result['user'] = user
                        result['reason'] = 'success'
                        result['match_info'] = mi
                        return result
        except Exception:
            pass

    # Strategy 2: ФИО без подразделения
    if is_initials:
        q = {
            'last_name__iexact': last_name,
            'first_name__istartswith': first_name_clean,
            'patronymic__istartswith': patronymic_clean,
        }
        found, user, mi = try_find_user(q, f"Ф={last_name}, И={first_name_clean}*, О={patronymic_clean}*")
        if found:
            result['found'] = True
            result['user'] = user
            result['reason'] = 'success'
            result['match_info'] = mi
            return result
    else:
        q = {
            'last_name__iexact': last_name,
            'first_name__iexact': first_name_clean,
            'patronymic__iexact': patronymic_clean,
        }
        found, user, mi = try_find_user(q, f"ФИО={last_name} {first_name_clean} {patronymic_clean}")
        if found:
            result['found'] = True
            result['user'] = user
            result['reason'] = 'success'
            result['match_info'] = mi
            return result

    # Strategy 3: Фамилия + Имя (без отчества)
    if is_initials:
        q = {
            'last_name__iexact': last_name,
            'first_name__istartswith': first_name_clean,
        }
        found, user, mi = try_find_user(q, f"Ф={last_name}, И={first_name_clean}*")
        if found:
            result['found'] = True
            result['user'] = user
            result['reason'] = 'success'
            result['match_info'] = mi
            return result
    else:
        q = {
            'last_name__iexact': last_name,
            'first_name__iexact': first_name_clean,
        }
        found, user, mi = try_find_user(q, f"ФИ={last_name} {first_name_clean}")
        if found:
            result['found'] = True
            result['user'] = user
            result['reason'] = 'success'
            result['match_info'] = mi
            return result

    # Strategy 4: Фамилия + подразделение
    if dept_name:
        try:
            dept = Department.objects.filter(
                name__icontains=dept_name
            ).first()
            if dept:
                result['match_info']['department_found'] = dept.name
                q = {
                    'last_name__iexact': last_name,
                    'department': dept,
                }
                found, user, mi = try_find_user(q, f"Ф={last_name}, Под={dept.name}")
                if found:
                    result['found'] = True
                    result['user'] = user
                    result['reason'] = 'success'
                    result['match_info'] = mi
                    return result
        except Exception:
            pass

    # Strategy 5: Только фамилия
    q = {'last_name__iexact': last_name}
    found, user, mi = try_find_user(q, f"Ф={last_name}")
    if found:
        result['found'] = True
        result['user'] = user
        result['reason'] = 'success'
        result['match_info'] = mi
        return result

    # No match found
    result['reason'] = 'not_found'
    result['match_info']['query'] = f"Попытки: Фамилия+И*+О*+Под, ФИО, Ф+И*, Фамилия"
    return result


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
    search_query = request.GET.get('q', '')
    from_inventory = request.GET.get('from_inventory', '')
    return render(request, 'equipment/equipment_edit_simple.html', {
        **_sidebar_counts(),
        'form': form,
        'instance': equipment,
        'equipment_type': equipment.category,
        'assigned_user': equipment.assigned_user,
        'mol_assignment': equipment.mol_assignments.filter(is_active=True).first(),
        'type_label': type_label,
        'search_query': search_query,
        'from_inventory': from_inventory,
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
    """AJAX назначение/замена пользователя на оборудовании."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    equipment = get_object_or_404(Equipment, pk=pk, archived=False)
    user_id = request.POST.get('user_id')
    action = request.POST.get('action', 'assign')
    
    if not user_id:
        return JsonResponse({'error': 'user_id required'}, status=400)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    if action == 'assign':
        # Проверяем, закреплен ли уже пользователь
        existing = equipment.assignments.filter(is_active=True, user=user).first()
        if existing:
            return JsonResponse({'error': 'User already assigned', 'already_assigned': True})
        
        # Создаём новое назначение
        EquipmentAssignment.objects.create(
            user=user,
            equipment=equipment,
            is_active=True,
        )
        # Обновляем поле assigned_user
        equipment.assigned_user = user
        equipment.save()
        
        return JsonResponse({
            'status': 'ok',
            'user_name': user.get_full_name(),
            'user_id': user.id,
            'action': 'assigned',
        })
    
    elif action == 'replace':
        # Деактивируем текущие назначения
        equipment.assignments.filter(is_active=True).update(is_active=False)
        
        # Создаём новое назначение
        EquipmentAssignment.objects.create(
            user=user,
            equipment=equipment,
            is_active=True,
        )
        equipment.assigned_user = user
        equipment.save()
        
        return JsonResponse({
            'status': 'ok',
            'user_name': user.get_full_name(),
            'user_id': user.id,
            'action': 'replaced',
        })
    
    return JsonResponse({'error': 'Invalid action'}, status=400)

def clear_assigned_user(request, equipment_type, pk):
    """Освобождение от пользователя."""
    equipment = get_object_or_404(Equipment, pk=pk, archived=False)
    
    # Деактивируем активные назначения
    equipment.assignments.filter(is_active=True).update(is_active=False)
    
    # Очищаем поле assigned_user
    equipment.assigned_user = None
    equipment.save()
    
    return redirect('equipment:edit', equipment_type=equipment_type, pk=pk)

def lookup_user_by_serial(request):
    """Стуб: поиск пользователя по серийному."""
    return JsonResponse({})

def search_users_ajax(request):
    """AJAX поиск пользователей по ФИО или табельному номеру."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET allowed'}, status=405)
    
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'users': []})
    
    # Поиск по ФИО или табельному номеру
    users = User.objects.filter(
        Q(last_name__icontains=query) |
        Q(first_name__icontains=query) |
        Q(patronymic__icontains=query) |
        Q(tab_number__icontains=query) |
        Q(username__icontains=query)
    ).distinct()[:50]
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'name': user.get_full_name(),
            'last_name': user.last_name,
            'first_name': user.first_name,
            'patronymic': user.patronymic,
            'tab_number': user.tab_number or '—',
            'username': user.username,
            'department': user.department.name if user.department else None,
            'position': user.position.name if user.position else None,
        })
    
    return JsonResponse({'users': users_data})

def quick_assign_users(request):
    """Стуб: быстрое назначение."""
    return JsonResponse({'status': 'ok'})

def equipment_detail(request, equipment_type, pk):
    """Детальная информация об оборудовании с учётом настроек полей."""
    equipment = get_object_or_404(Equipment, pk=pk, archived=False)
    visible_fields = equipment.get_visible_fields(for_edit=False)

    # Добавляем значения полей с форматированием
    for field in visible_fields:
        val = getattr(equipment, field['name'], None)
        # Форматирование значений
        if isinstance(val, bool):
            field['value'] = 'Да' if val else 'Нет'
        elif hasattr(val, 'name'):
            field['value'] = val.name
        elif hasattr(val, '__str__'):
            field['value'] = str(val)
        else:
            field['value'] = val
        
        # Для поля os добавляем версию из SIEM в скобках
        if field['name'] == 'os' and equipment.siem_host and equipment.siem_host.os_info:
            siem_version = equipment.siem_host.os_info.strip()
            if siem_version and field['value']:
                field['value'] = f"{field['value']} ({siem_version})"

    # Бухгалтерские данные
    accounting_data = {
        'acquisition_date': equipment.acquisition_date,
        'acquisition_cost': equipment.acquisition_cost,
        'initial_number': equipment.initial_number,
        'useful_life_months': equipment.useful_life_months,
        'depreciation_method': equipment.depreciation_method,
        'decommission_date': equipment.decommission_date,
        'decommission_act': equipment.decommission_act,
        'decommission_notes': equipment.decommission_notes,
        'decommissioned_by': equipment.decommissioned_by,
    }

    # История списаний
    decommission_records = equipment.decommission_records.order_by('-created_at')[:10]

    # История перемещений
    movements = equipment.movements.order_by('-move_datetime')[:20]

    # История ремонтов
    repairs = equipment.repairs.order_by('-created_at')[:20]

    # История модернизаций
    upgrades = equipment.upgrades.order_by('-created_at')[:20]

    return render(request, 'equipment/equipment_detail.html', {
        **_sidebar_counts(),
        'instance': equipment,
        'visible_fields': visible_fields,
        'accounting': accounting_data,
        'decommission_records': decommission_records,
        'movements': movements,
        'repairs': repairs,
        'upgrades': upgrades,
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
    """AJAX назначение МОЛ."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    equipment = get_object_or_404(Equipment, pk=pk, archived=False)
    user_id = request.POST.get('user_id')
    action = request.POST.get('action', 'assign')
    
    if not user_id:
        return JsonResponse({'error': 'user_id required'}, status=400)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    if action == 'assign':
        # Проверяем, назначен ли уже пользователь как МОЛ
        existing = equipment.mol_assignments.filter(is_active=True, mol=user).first()
        if existing:
            return JsonResponse({'error': 'User already MOL', 'already_assigned': True})
        
        # Создаём новое назначение МОЛ
        EquipmentMOLAssignment.objects.create(
            mol=user,
            equipment=equipment,
            is_active=True,
        )
        # Обновляем поле responsible_user
        equipment.responsible_user = user
        equipment.save()
        
        return JsonResponse({
            'status': 'ok',
            'user_name': user.get_full_name(),
            'user_id': user.id,
            'action': 'assigned',
        })
    
    elif action == 'replace':
        # Деактивируем текущие назначения МОЛ
        equipment.mol_assignments.filter(is_active=True).update(is_active=False)
        
        # Создаём новое назначение МОЛ
        EquipmentMOLAssignment.objects.create(
            mol=user,
            equipment=equipment,
            is_active=True,
        )
        equipment.responsible_user = user
        equipment.save()
        
        return JsonResponse({
            'status': 'ok',
            'user_name': user.get_full_name(),
            'user_id': user.id,
            'action': 'replaced',
        })
    
    return JsonResponse({'error': 'Invalid action'}, status=400)

def change_responsible_user_ajax(request, equipment_type, pk):
    """AJAX изменение ответственного (МОЛ)."""
    return assign_mol_ajax(request, equipment_type, pk)

def clear_responsible_user(request, equipment_type, pk):
    """Освобождение от МОЛ."""
    equipment = get_object_or_404(Equipment, pk=pk, archived=False)
    
    # Деактивируем активные назначения МОЛ
    equipment.mol_assignments.filter(is_active=True).update(is_active=False)
    
    # Очищаем поле responsible_user
    equipment.responsible_user = None
    equipment.save()
    
    return JsonResponse({'status': 'ok', 'action': 'cleared'})

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
# Инвентаризация — Закрепленное оборудование
# ============================================================================

@login_required
def assigned_equipment(request):
    """Закрепленное оборудование — список оборудования с назначенными пользователями."""
    # Фильтры
    search = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '').strip()
    subcategory_filter = request.GET.get('subcategory', '').strip()
    sort = request.GET.get('sort', '').strip()
    
    # Определяем порядок сортировки
    valid_sorts = {
        'inventory_number': 'inventory_number',
        '-inventory_number': '-inventory_number',
        'name': 'name',
        '-name': '-name',
        'category': 'category__name',
        '-category': '-category__name',
        'assigned_user': 'assigned_user__last_name',
        '-assigned_user': '-assigned_user__last_name',
        'responsible_user': 'responsible_user__last_name',
        '-responsible_user': '-responsible_user__last_name',
        'serial_number': 'serial_number',
        '-serial_number': '-serial_number',
    }
    
    if sort in valid_sorts:
        equipment_qs = Equipment.objects.filter(
            Q(assigned_user__isnull=False) | Q(responsible_user__isnull=False),
            archived=False
        ).select_related(
            'assigned_user', 'responsible_user', 'category', 'subcategory', 'brand'
        ).order_by(valid_sorts[sort])
    else:
        equipment_qs = Equipment.objects.filter(
            Q(assigned_user__isnull=False) | Q(responsible_user__isnull=False),
            archived=False
        ).select_related(
            'assigned_user', 'responsible_user', 'category', 'subcategory', 'brand'
        ).order_by('-is_active', 'category', 'inventory_number')
    
    if search:
        equipment_qs = equipment_qs.filter(
            Q(name__icontains=search) |
            Q(inventory_number__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(assigned_user__first_name__icontains=search) |
            Q(assigned_user__last_name__icontains=search) |
            Q(assigned_user__patronymic__icontains=search) |
            Q(responsible_user__first_name__icontains=search) |
            Q(responsible_user__last_name__icontains=search) |
            Q(responsible_user__patronymic__icontains=search)
        )
    
    if category_filter:
        equipment_qs = equipment_qs.filter(category__slug=category_filter)
    
    if subcategory_filter:
        equipment_qs = equipment_qs.filter(subcategory__slug=subcategory_filter)

    # Пагинация: 20 записей на страницу
    page_number = request.GET.get('page', 1)
    paginator = Paginator(equipment_qs, 20)
    page_obj = paginator.get_page(page_number)

    # Статистика
    total_assigned = equipment_qs.count()
    by_user = equipment_qs.values('assigned_user__first_name', 'assigned_user__last_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    by_category = equipment_qs.values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    context = {
        **_sidebar_counts(),
        'equipment_list': page_obj.object_list,
        'total_count': total_assigned,
        'by_user': by_user,
        'by_category': by_category,
        'current_search': search,
        'current_category': category_filter,
        'current_subcategory': subcategory_filter,
        'current_sort': sort,
        'page_obj': page_obj,
        'all_categories': EquipmentCategory.objects.filter(
            parent__isnull=True, is_active=True
        ).values_list('slug', 'name'),
        'all_subcategories': EquipmentCategory.objects.filter(
            parent__isnull=False, is_active=True
        ).select_related('parent').values_list('slug', 'name', 'parent__slug'),
        'all_subcategories_json': json.dumps([
            {'slug': sc['slug'], 'name': sc['name']}
            for sc in EquipmentCategory.objects.filter(
                parent__isnull=False, is_active=True
            ).values('slug', 'name')
        ]),
    }
    return render(request, 'equipment/assigned_equipment.html', context)


# ============================================================================
# Инвентаризация — Инвентаризационный поиск
# ============================================================================

@login_required
def inventory_search(request):
    """Инвентаризационный поиск — поиск оборудования по всем полям."""
    search_query = request.GET.get('q', '').strip()

    equipment_qs = Equipment.objects.filter(archived=False).select_related(
        'assigned_user', 'responsible_user', 'category', 'subcategory', 'brand'
    ).order_by('-is_active', 'category', 'inventory_number')

    if search_query:
        equipment_qs = equipment_qs.filter(
            Q(name__icontains=search_query) |
            Q(inventory_number__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(hostname__icontains=search_query) |
            Q(mac_address__icontains=search_query) |
            Q(ip_address__icontains=search_query) |
            Q(model__icontains=search_query) |
            Q(brand__name__icontains=search_query) |
            Q(cpu__icontains=search_query) |
            Q(os__icontains=search_query) |
            Q(antivirus_engine__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(place__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(extension__icontains=search_query) |
            Q(status__icontains=search_query) |
            Q(assigned_user__first_name__icontains=search_query) |
            Q(assigned_user__last_name__icontains=search_query) |
            Q(responsible_user__first_name__icontains=search_query) |
            Q(responsible_user__last_name__icontains=search_query)
        )

    # Пагинация: 10 записей на страницу
    page_number = request.GET.get('page', 1)
    paginator = Paginator(equipment_qs, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        **_sidebar_counts(),
        'equipment_list': page_obj.object_list,
        'total_count': equipment_qs.count(),
        'search_query': search_query,
        'page_obj': page_obj,
    }
    return render(request, 'equipment/inventory_search.html', context)


# ============================================================================
# Управление настройками полей
# ============================================================================

@login_required
def field_settings(request):
    """Управление настройками отображения полей для подкатегорий оборудования."""
    if request.method == 'POST':
        # Обновляем настройки
        subcategory_id = request.POST.get('subcategory_id')
        subcat = EquipmentCategory.objects.filter(pk=subcategory_id, is_active=True).first()
        if not subcat:
            messages.error(request, 'Выберите подкатегорию')
            return redirect('equipment:field_settings')
        
        for field_name in ['inventory_number', 'serial_number', 'name', 'brand', 'model',
                          'assigned_user', 'responsible_user', 'hostname', 'mac_address', 'ip_address',
                          'cpu', 'ram_gb', 'storage_gb', 'screen_size', 'os', 'os_version',
                          'antivirus_engine', 'antivirus_active', 'resolution', 'printer_status',
                          'camera_count', 'phone_number', 'extension', 'calibration_date',
                          'next_calibration', 'status', 'is_active', 'archived', 'last_scan']:
            is_visible = request.POST.get(f'visible_{subcategory_id}_{field_name}', 'on') == 'on'
            is_editable = request.POST.get(f'editable_{subcategory_id}_{field_name}', 'on') == 'on'
            
            setting, created = EquipmentFieldSetting.objects.get_or_create(
                subcategory=subcat,
                field_name=field_name,
                defaults={
                    'is_visible': is_visible,
                    'is_editable': is_editable,
                }
            )
            if not created:
                setting.is_visible = is_visible
                setting.is_editable = is_editable
                setting.save()
        
        messages.success(request, 'Настройки полей сохранены')
        return redirect('equipment:field_settings')
    
    # Загружаем текущие настройки
    subcategories = EquipmentCategory.objects.filter(
        parent__isnull=False, is_active=True
    ).order_by('parent', 'name')
    
    settings_data = {}
    for subcat in subcategories:
        settings = EquipmentFieldSetting.objects.filter(subcategory=subcat)
        settings_map = {s.field_name: s for s in settings}
        settings_data[subcat.pk] = {
            'label': subcat.name,
            'parent': subcat.parent.name if subcat.parent else '',
            'fields': [],
        }
        
        field_defs = [
            ('inventory_number', 'Инвентарный номер', 'Основное'),
            ('serial_number', 'Серийный номер', 'Основное'),
            ('name', 'Название', 'Основное'),
            ('brand', 'Бренд', 'Основное'),
            ('model', 'Модель', 'Основное'),
            ('hostname', 'Имя в сети', 'Сеть'),
            ('mac_address', 'MAC-адрес', 'Сеть'),
            ('ip_address', 'IP-адрес', 'Сеть'),
            ('cpu', 'Процессор', 'Характеристики'),
            ('ram_gb', 'ОЗУ (ГБ)', 'Характеристики'),
            ('storage_gb', 'Диск (ГБ)', 'Характеристики'),
            ('screen_size', 'Диагональ экрана', 'Характеристики'),
            ('os', 'ОС', 'Программное обеспечение'),
            ('os_version', 'Версия ОС', 'Программное обеспечение'),
            ('antivirus_engine', 'Антивирус', 'Программное обеспечение'),
            ('antivirus_active', 'Защита активна', 'Программное обеспечение'),
            ('resolution', 'Разрешение', 'Характеристики'),
            ('printer_status', 'Статус принтера', 'Статус'),
            ('camera_count', 'Количество камер', 'Характеристики'),
            ('phone_number', 'Внешний номер', 'Телефон'),
            ('extension', 'Внутренний номер', 'Телефон'),
            ('status', 'Статус', 'Статус'),
        ]
        
        for field_name, field_label, field_group in field_defs:
            setting = settings_map.get(field_name)
            if setting:
                settings_data[subcat.pk]['fields'].append({
                    'name': field_name,
                    'label': field_label,
                    'group': field_group,
                    'is_visible': setting.is_visible,
                    'is_editable': setting.is_editable,
                })
            else:
                settings_data[subcat.pk]['fields'].append({
                    'name': field_name,
                    'label': field_label,
                    'group': field_group,
                    'is_visible': True,
                    'is_editable': True,
                })
    
    context = {
        **_sidebar_counts(),
        'settings_data': settings_data,
        'default_subcategory': subcategories.first().pk if subcategories.exists() else None,
    }
    return render(request, 'equipment/field_settings.html', context)


# ============================================================================
# Справочник расположения (город → корпус → этаж → кабинет)
# ============================================================================

@login_required
def location_list(request):
    """Иерархический справочник расположения: город → корпус → этаж → кабинет."""
    cities = City.objects.filter(is_active=True).prefetch_related(
        'buildings__floors__rooms'
    ).order_by('name')

    location_data = []
    for city in cities:
        city_data = {
            'pk': city.pk,
            'name': city.name,
            'code': city.code,
            'buildings_count': city.buildings_count,
            'buildings': [],
        }
        for building in city.buildings.filter(is_active=True).order_by('name'):
            building_data = {
                'pk': building.pk,
                'name': building.name,
                'code': building.code,
                'address': building.address,
                'floors_count': building.floors_count,
                'rooms_count': building.rooms_count,
                'floors': [],
            }
            for floor in building.floors.filter(is_active=True).order_by('floor_number'):
                floor_data = {
                    'pk': floor.pk,
                    'floor_number': floor.floor_number,
                    'rooms_count': floor.rooms_count,
                    'rooms': [],
                }
                for room in floor.rooms.filter(is_active=True).order_by('room_number'):
                    floor_data['rooms'].append({
                        'pk': room.pk,
                        'room_number': room.room_number,
                        'capacity': room.capacity,
                    })
                building_data['floors'].append(floor_data)
            city_data['buildings'].append(building_data)
        location_data.append(city_data)

    context = {
        **_sidebar_counts(),
        'location_data': location_data,
    }
    return render(request, 'equipment/location_list.html', context)


@login_required
def location_city_add(request):
    """Добавление города."""
    if request.method == 'POST':
        form = CityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Город успешно добавлен')
            return redirect('equipment:location_list')
    else:
        form = CityForm()

    return render(request, 'equipment/location_form.html', {
        **_sidebar_counts(),
        'form': form,
        'title': 'Добавить город',
        'model_type': 'city',
    })


@login_required
def location_city_edit(request, pk):
    """Редактирование города."""
    city = get_object_or_404(City, pk=pk)
    if request.method == 'POST':
        form = CityForm(request.POST, instance=city)
        if form.is_valid():
            form.save()
            messages.success(request, 'Город успешно обновлён')
            return redirect('equipment:location_list')
    else:
        form = CityForm(instance=city)

    return render(request, 'equipment/location_form.html', {
        **_sidebar_counts(),
        'form': form,
        'instance': city,
        'title': 'Редактировать город',
        'model_type': 'city',
    })


@login_required
def location_city_delete(request, pk):
    """Удаление города (мягкое)."""
    city = get_object_or_404(City, pk=pk)
    city.is_active = False
    city.save()
    messages.success(request, 'Город удалён')
    return redirect('equipment:location_list')


@login_required
def location_building_add(request):
    """Добавление корпуса."""
    if request.method == 'POST':
        form = BuildingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Корпус успешно добавлен')
            return redirect('equipment:location_list')
    else:
        city_id = request.GET.get('city')
        form = BuildingForm(initial={'city': city_id} if city_id else {})

    return render(request, 'equipment/location_form.html', {
        **_sidebar_counts(),
        'form': form,
        'title': 'Добавить корпус',
        'model_type': 'building',
    })


@login_required
def location_building_edit(request, pk):
    """Редактирование корпуса."""
    building = get_object_or_404(Building, pk=pk)
    if request.method == 'POST':
        form = BuildingForm(request.POST, instance=building)
        if form.is_valid():
            form.save()
            messages.success(request, 'Корпус успешно обновлён')
            return redirect('equipment:location_list')
    else:
        form = BuildingForm(instance=building)

    return render(request, 'equipment/location_form.html', {
        **_sidebar_counts(),
        'form': form,
        'instance': building,
        'title': 'Редактировать корпус',
        'model_type': 'building',
    })


@login_required
def location_building_delete(request, pk):
    """Удаление корпуса (мягкое)."""
    building = get_object_or_404(Building, pk=pk)
    building.is_active = False
    building.save()
    messages.success(request, 'Корпус удалён')
    return redirect('equipment:location_list')


@login_required
def location_floor_add(request):
    """Добавление этажа."""
    if request.method == 'POST':
        form = FloorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Этаж успешно добавлен')
            return redirect('equipment:location_list')
    else:
        building_id = request.GET.get('building')
        form = FloorForm(initial={'building': building_id} if building_id else {})

    return render(request, 'equipment/location_form.html', {
        **_sidebar_counts(),
        'form': form,
        'title': 'Добавить этаж',
        'model_type': 'floor',
    })


@login_required
def location_floor_edit(request, pk):
    """Редактирование этажа."""
    floor = get_object_or_404(Floor, pk=pk)
    if request.method == 'POST':
        form = FloorForm(request.POST, instance=floor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Этаж успешно обновлён')
            return redirect('equipment:location_list')
    else:
        form = FloorForm(instance=floor)

    return render(request, 'equipment/location_form.html', {
        **_sidebar_counts(),
        'form': form,
        'instance': floor,
        'title': 'Редактировать этаж',
        'model_type': 'floor',
    })


@login_required
def location_floor_delete(request, pk):
    """Удаление этажа (мягкое)."""
    floor = get_object_or_404(Floor, pk=pk)
    floor.is_active = False
    floor.save()
    messages.success(request, 'Этаж удалён')
    return redirect('equipment:location_list')


@login_required
def location_room_add(request):
    """Добавление кабинета."""
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Кабинет успешно добавлен')
            return redirect('equipment:location_list')
    else:
        building_id = request.GET.get('building')
        floor_id = request.GET.get('floor')
        initial = {}
        if building_id:
            initial['building'] = building_id
        if floor_id:
            initial['floor'] = floor_id
        form = RoomForm(initial=initial)

    # Получаем корпуса для AJAX подгрузки
    buildings = Building.objects.filter(is_active=True).order_by('city', 'name')
    floors = Floor.objects.none()
    if building_id:
        floors = Floor.objects.filter(building_id=building_id, is_active=True).order_by('floor_number')

    return render(request, 'equipment/location_form.html', {
        **_sidebar_counts(),
        'form': form,
        'title': 'Добавить кабинет',
        'model_type': 'room',
        'buildings': buildings,
        'floors': floors,
    })


@login_required
def location_room_edit(request, pk):
    """Редактирование кабинета."""
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, 'Кабинет успешно обновлён')
            return redirect('equipment:location_list')
    else:
        form = RoomForm(instance=room)

    buildings = Building.objects.filter(is_active=True).order_by('city', 'name')
    floors = Floor.objects.filter(building_id=room.building_id, is_active=True).order_by('floor_number')

    return render(request, 'equipment/location_form.html', {
        **_sidebar_counts(),
        'form': form,
        'instance': room,
        'title': 'Редактировать кабинет',
        'model_type': 'room',
        'buildings': buildings,
        'floors': floors,
    })


@login_required
def location_room_delete(request, pk):
    """Удаление кабинета (мягкое)."""
    room = get_object_or_404(Room, pk=pk)
    room.is_active = False
    room.save()
    messages.success(request, 'Кабинет удалён')
    return redirect('equipment:location_list')


@login_required
def get_floors_ajax(request):
    """AJAX: получить этажи для корпуса."""
    building_id = request.GET.get('building_id')
    floors = Floor.objects.filter(
        building_id=building_id, is_active=True
    ).order_by('floor_number')
    data = [
        {'pk': f.pk, 'floor_number': f.floor_number}
        for f in floors
    ]
    return JsonResponse(data, safe=False)


# ============================================================================
# AJAX endpoints для категорий оборудования
# ============================================================================

@login_required
def get_subcategories_ajax(request):
    """AJAX: получить подкатегории для категории."""
    category_slug = request.GET.get('category_slug')
    if not category_slug:
        return JsonResponse([], safe=False)
    
    category = EquipmentCategory.objects.filter(
        slug=category_slug, is_active=True
    ).first()
    
    if not category:
        return JsonResponse([], safe=False)
    
    subcategories = category.children.filter(is_active=True).order_by('name')
    data = [
        {'pk': sc.pk, 'name': sc.name, 'slug': sc.slug}
        for sc in subcategories
    ]
    return JsonResponse(data, safe=False)


@login_required
def get_categories_ajax(request):
    """AJAX: получить все категории (для фильтров)."""
    categories = EquipmentCategory.objects.filter(
        parent__isnull=True, is_active=True
    ).prefetch_related('children').order_by('name')
    
    data = []
    for cat in categories:
        subcategories = cat.children.filter(is_active=True).order_by('name')
        data.append({
            'pk': cat.pk,
            'name': cat.name,
            'slug': cat.slug,
            'is_top_level': True,
            'children': [
                {'pk': sc.pk, 'name': sc.name, 'slug': sc.slug}
                for sc in subcategories
            ],
        })
    return JsonResponse(data, safe=False)


# ============================================================================
# CRUD справочник категорий оборудования
# ============================================================================

@login_required
def category_list(request):
    """Справочник категорий оборудования с возможностью редактирования."""
    # Получаем все категории (включая архивные)
    all_categories = EquipmentCategory.objects.all().prefetch_related('children').order_by('parent', 'name')
    
    # Фильтр: показать все / только активные / только архивные
    show = request.GET.get('show', 'active')  # active, archived, all
    
    if show == 'archived':
        categories = EquipmentCategory.objects.filter(is_active=False).prefetch_related('children').order_by('parent', 'name')
    elif show == 'all':
        categories = EquipmentCategory.objects.all().prefetch_related('children').order_by('parent', 'name')
    else:
        categories = EquipmentCategory.objects.filter(is_active=True).prefetch_related('children').order_by('parent', 'name')
    
    # Группируем по родительским категориям
    category_tree = []
    top_categories = categories.filter(parent__isnull=True).order_by('name')
    
    for top_cat in top_categories:
        top_data = {
            'pk': top_cat.pk,
            'name': top_cat.name,
            'slug': top_cat.slug,
            'is_active': top_cat.is_active,
            'equipment_count': Equipment.objects.filter(category=top_cat, archived=False).count(),
            'children': [],
        }
        for child in top_cat.children.filter(is_active=True if show != 'all' else None).order_by('name'):
            child_data = {
                'pk': child.pk,
                'name': child.name,
                'slug': child.slug,
                'is_active': child.is_active,
                'equipment_count': Equipment.objects.filter(subcategory=child, archived=False).count(),
            }
            top_data['children'].append(child_data)
        category_tree.append(top_data)
    
    # Показываем категории без родителя (на всякий случай)
    orphan_cats = categories.filter(parent__isnull=True).exclude(
        pk__in=[c['pk'] for c in category_tree]
    ).order_by('name')
    
    context = {
        **_sidebar_counts(),
        'category_tree': category_tree,
        'orphan_categories': orphan_cats,
        'current_show': show,
    }
    return render(request, 'equipment/category_list.html', context)


@login_required
def category_add(request):
    """Добавление категории."""
    parent_id = request.GET.get('parent')
    
    if request.method == 'POST':
        form = EquipmentCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Категория успешно добавлена')
            return redirect('equipment:category_list')
    else:
        initial = {}
        if parent_id:
            initial['parent'] = parent_id
        form = EquipmentCategoryForm(initial=initial)

    # Получаем родительские категории для формы
    parents = EquipmentCategory.objects.filter(
        parent__isnull=True, is_active=True
    ).order_by('name')

    return render(request, 'equipment/category_form.html', {
        **_sidebar_counts(),
        'form': form,
        'title': 'Добавить категорию',
        'parents': parents,
        'model_type': 'category',
    })


@login_required
def category_edit(request, pk):
    """Редактирование категории."""
    category = get_object_or_404(EquipmentCategory, pk=pk)
    
    if request.method == 'POST':
        form = EquipmentCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Категория успешно обновлена')
            return redirect('equipment:category_list')
    else:
        form = EquipmentCategoryForm(instance=category)

    parents = EquipmentCategory.objects.filter(
        parent__isnull=True, is_active=True
    ).exclude(pk=category.pk).order_by('name')

    return render(request, 'equipment/category_form.html', {
        **_sidebar_counts(),
        'form': form,
        'instance': category,
        'title': 'Редактировать категорию',
        'parents': parents,
        'model_type': 'category',
    })


@login_required
def category_delete(request, pk):
    """Удаление категории (мягкое)."""
    category = get_object_or_404(EquipmentCategory, pk=pk)
    
    # Проверяем, привязана ли техника
    equipment_count = Equipment.objects.filter(
        Q(category=category) | Q(subcategory=category),
        archived=False
    ).count()
    
    if equipment_count > 0:
        messages.error(request, f'Нельзя удалить категорию: за ней закреплено {equipment_count} единиц техники')
    else:
        category.is_active = False
        category.save()
        messages.success(request, 'Категория перемещена в архив')
    
    return redirect('equipment:category_list')


@login_required
def category_restore(request, pk):
    """Восстановление категории из архива."""
    category = get_object_or_404(EquipmentCategory, pk=pk, is_active=False)
    category.is_active = True
    category.save()
    messages.success(request, 'Категория восстановлена')
    return redirect('equipment:category_list')


# ============================================================================
# Список оборудования по категории первого уровня
# ============================================================================

@login_required
def category_equipment_list(request, category_slug):
    """Список оборудования по категории первого уровня."""
    category = get_object_or_404(
        EquipmentCategory, slug=category_slug, is_active=True
    )
    
    equipment_qs = Equipment.objects.filter(
        category=category,
        archived=False,
    ).select_related(
        'assigned_user', 'responsible_user', 'brand', 'category', 'subcategory'
    ).order_by('-is_active', 'subcategory', 'inventory_number')
    
    # Подкатегории для фильтра
    subcategories = category.children.filter(is_active=True).order_by('name')
    
    # Фильтр по подкатегории
    sub_slug = request.GET.get('subcategory')
    if sub_slug:
        subcat = get_object_or_404(
            EquipmentCategory, slug=sub_slug, is_active=True
        )
        equipment_qs = equipment_qs.filter(subcategory=subcat)
    
    # Поиск
    search = request.GET.get('search', '').strip()
    if search:
        equipment_qs = equipment_qs.filter(
            Q(inventory_number__icontains=search)
            | Q(serial_number__icontains=search)
            | Q(name__icontains=search)
            | Q(brand__name__icontains=search)
            | Q(model__icontains=search)
            | Q(hostname__icontains=search)
            | Q(ip_address__icontains=search)
            | Q(location__icontains=search)
        )
    
    total_count = equipment_qs.count()
    
    # Статистика по подкатегориям
    sub_stats = []
    for subcat in subcategories:
        sub_stats.append({
            'slug': subcat.slug,
            'name': subcat.name,
            'count': Equipment.objects.filter(
                category=category, subcategory=subcat, archived=False
            ).count(),
        })
    
    context = {
        **_sidebar_counts(),
        'category': category,
        'equipment_list': equipment_qs,
        'total_count': total_count,
        'subcategories': subcategories,
        'sub_stats': sub_stats,
        'current_subcategory': sub_slug,
        'current_search': search,
    }
    return render(request, 'equipment/category_equipment_list.html', context)


# ============================================================================
# Справочник исключений (второй уровень фильтрации)
# ============================================================================

@login_required
def exclude_keywords_reference(request):
    """Справочник ключевых слов исключений (второй уровень фильтрации)."""
    # Статистика по категориям
    categories = ExcludeKeyword.objects.values_list('category', flat=True).distinct().order_by('category')
    category_stats = {}
    for cat in categories:
        count = ExcludeKeyword.objects.filter(category=cat, is_active=True).count()
        category_stats[cat] = count

    # Получаем все активные исключения, сгруппированные по категориям
    keywords = ExcludeKeyword.objects.all().order_by('category', 'keyword')
    grouped_keywords = {}
    for kw in keywords:
        if kw.category not in grouped_keywords:
            grouped_keywords[kw.category] = []
        grouped_keywords[kw.category].append(kw)

    context = {
        **_sidebar_counts(),
        'grouped_keywords_items': list(grouped_keywords.items()),
        'category_stats': category_stats,
        'total_active': ExcludeKeyword.objects.filter(is_active=True).count(),
        'total_all': ExcludeKeyword.objects.count(),
    }
    return render(request, 'equipment/exclude_keywords_reference.html', context)


@login_required
def exclude_keyword_add(request):
    """Добавление ключевого слова исключения."""
    if request.method == 'POST':
        keyword = request.POST.get('keyword', '').strip()
        category = request.POST.get('category', '').strip()
        is_active = request.POST.get('is_active', 'on') == 'on'
        
        if not keyword:
            messages.error(request, 'Введите ключевое слово')
            return redirect('equipment:exclude_keywords_reference')
        
        # Проверяем дубликат
        if ExcludeKeyword.objects.filter(keyword__iexact=keyword).exists():
            messages.error(request, f'Исключение "{keyword}" уже существует')
            return redirect('equipment:exclude_keywords_reference')
        
        ExcludeKeyword.objects.create(
            keyword=keyword,
            category=category,
            is_active=is_active,
        )
        messages.success(request, f'Исключение "{keyword}" добавлено')
        return redirect('equipment:exclude_keywords_reference')
    
    return redirect('equipment:exclude_keywords_reference')


@login_required
def exclude_keyword_edit(request, pk):
    """Редактирование ключевого слова исключения."""
    kw = get_object_or_404(ExcludeKeyword, pk=pk)
    
    if request.method == 'POST':
        kw.keyword = request.POST.get('keyword', '').strip()
        kw.category = request.POST.get('category', '').strip()
        kw.is_active = request.POST.get('is_active', 'on') == 'on'
        
        if not kw.keyword:
            messages.error(request, 'Введите ключевое слово')
            return redirect('equipment:exclude_keywords_reference')
        
        # Проверяем дубликат (исключая текущую запись)
        if ExcludeKeyword.objects.filter(keyword__iexact=kw.keyword).exclude(pk=pk).exists():
            messages.error(request, f'Исключение "{kw.keyword}" уже существует')
            return redirect('equipment:exclude_keywords_reference')
        
        kw.save()
        messages.success(request, f'Исключение "{kw.keyword}" обновлено')
        return redirect('equipment:exclude_keywords_reference')
    
    # GET запрос — показываем справочник с модальным окном редактирования
    categories = ExcludeKeyword.objects.values_list('category', flat=True).distinct().order_by('category')
    category_stats = {}
    for cat in categories:
        count = ExcludeKeyword.objects.filter(category=cat, is_active=True).count()
        category_stats[cat] = count

    keywords = ExcludeKeyword.objects.all().order_by('category', 'keyword')
    grouped_keywords = {}
    for k in keywords:
        if k.category not in grouped_keywords:
            grouped_keywords[k.category] = []
        grouped_keywords[k.category].append(k)

    context = {
        **_sidebar_counts(),
        'grouped_keywords_items': list(grouped_keywords.items()),
        'category_stats': category_stats,
        'total_active': ExcludeKeyword.objects.filter(is_active=True).count(),
        'total_all': ExcludeKeyword.objects.count(),
        'edit_kw': kw,  # Для модального окна редактирования
    }
    return render(request, 'equipment/exclude_keywords_reference.html', context)


@login_required
def exclude_keyword_delete(request, pk):
    """Удаление ключевого слова исключения."""
    kw = get_object_or_404(ExcludeKeyword, pk=pk)
    keyword = kw.keyword
    kw.delete()
    messages.success(request, f'Исключение "{keyword}" удалено')
    return redirect('equipment:exclude_keywords_reference')


@login_required
def exclude_keyword_toggle(request, pk):
    """Переключение активности ключевого слова."""
    kw = get_object_or_404(ExcludeKeyword, pk=pk)
    kw.is_active = not kw.is_active
    kw.save()
    status = 'активировано' if kw.is_active else 'деактивировано'
    messages.success(request, f'Исключение "{kw.keyword}" {status}')
    return redirect('equipment:exclude_keywords_reference')


# ============================================================================
# Справочник ключевых слов фильтрации наименований (первый уровень)
# ============================================================================

@login_required
def filter_keywords_reference(request):
    """Справочник ключевых слов фильтрации наименований."""
    categories = FilterKeyword.objects.values_list('category', flat=True).distinct().order_by('category')
    category_stats = {}
    for cat in categories:
        count = FilterKeyword.objects.filter(category=cat, is_active=True).count()
        category_stats[cat] = count

    keywords = FilterKeyword.objects.all().order_by('category', 'keyword')
    grouped_keywords = {}
    for kw in keywords:
        if kw.category not in grouped_keywords:
            grouped_keywords[kw.category] = []
        grouped_keywords[kw.category].append(kw)

    # Добавляем отображаемые названия категорий
    category_labels = {cat: label for cat, label in FilterKeyword.CATEGORY_CHOICES}
    
    # Добавляем display_name к каждой группе
    grouped_with_labels = []
    for cat, kws in grouped_keywords.items():
        grouped_with_labels.append((category_labels.get(cat, cat), kws))

    context = {
        **_sidebar_counts(),
        'grouped_keywords_items': grouped_with_labels,
        'category_stats': category_stats,
        'total_active': FilterKeyword.objects.filter(is_active=True).count(),
        'total_all': FilterKeyword.objects.count(),
        'CATEGORY_CHOICES': dict(FilterKeyword.CATEGORY_CHOICES),
        'category_labels': category_labels,
    }
    return render(request, 'equipment/filter_keywords_reference.html', context)


@login_required
def filter_keyword_add(request):
    """Добавление ключевого слова фильтрации."""
    if request.method == 'POST':
        keyword = request.POST.get('keyword', '').strip()
        category = request.POST.get('category', '')
        is_active = request.POST.get('is_active', 'on') == 'on'
        
        if not keyword:
            messages.error(request, 'Введите ключевое слово')
            return redirect('equipment:filter_keywords_reference')
        
        if not category:
            messages.error(request, 'Выберите категорию')
            return redirect('equipment:filter_keywords_reference')
        
        if FilterKeyword.objects.filter(keyword__iexact=keyword, category=category).exists():
            messages.error(request, f'Ключевое слово "{keyword}" уже существует в категории')
            return redirect('equipment:filter_keywords_reference')
        
        FilterKeyword.objects.create(
            keyword=keyword,
            category=category,
            is_active=is_active,
        )
        messages.success(request, f'Ключевое слово "{keyword}" добавлено')
        return redirect('equipment:filter_keywords_reference')
    
    return redirect('equipment:filter_keywords_reference')


@login_required
def filter_keyword_edit(request, pk):
    """Редактирование ключевого слова фильтрации."""
    kw = get_object_or_404(FilterKeyword, pk=pk)
    
    if request.method == 'POST':
        kw.keyword = request.POST.get('keyword', '').strip()
        kw.category = request.POST.get('category', '')
        kw.is_active = request.POST.get('is_active', 'on') == 'on'
        
        if not kw.keyword or not kw.category:
            messages.error(request, 'Заполните все поля')
            return redirect('equipment:filter_keywords_reference')
        
        if FilterKeyword.objects.filter(keyword__iexact=kw.keyword, category=kw.category).exclude(pk=pk).exists():
            messages.error(request, f'Ключевое слово "{kw.keyword}" уже существует')
            return redirect('equipment:filter_keywords_reference')
        
        kw.save()
        messages.success(request, f'Ключевое слово "{kw.keyword}" обновлено')
        return redirect('equipment:filter_keywords_reference')
    
    # GET — показываем справочник с модальным окном
    categories = FilterKeyword.objects.values_list('category', flat=True).distinct().order_by('category')
    category_stats = {}
    for cat in categories:
        count = FilterKeyword.objects.filter(category=cat, is_active=True).count()
        category_stats[cat] = count

    keywords = FilterKeyword.objects.all().order_by('category', 'keyword')
    grouped_keywords = {}
    for k in keywords:
        if k.category not in grouped_keywords:
            grouped_keywords[k.category] = []
        grouped_keywords[k.category].append(k)

    category_labels = {cat: label for cat, label in FilterKeyword.CATEGORY_CHOICES}
    
    grouped_with_labels = []
    for cat, kws in grouped_keywords.items():
        grouped_with_labels.append((category_labels.get(cat, cat), kws))

    context = {
        **_sidebar_counts(),
        'grouped_keywords_items': grouped_with_labels,
        'category_stats': category_stats,
        'total_active': FilterKeyword.objects.filter(is_active=True).count(),
        'total_all': FilterKeyword.objects.count(),
        'CATEGORY_CHOICES': dict(FilterKeyword.CATEGORY_CHOICES),
        'category_labels': category_labels,
        'edit_kw': kw,
    }
    return render(request, 'equipment/filter_keywords_reference.html', context)


@login_required
def filter_keyword_delete(request, pk):
    """Удаление ключевого слова фильтрации."""
    kw = get_object_or_404(FilterKeyword, pk=pk)
    keyword = kw.keyword
    kw.delete()
    messages.success(request, f'Ключевое слово "{keyword}" удалено')
    return redirect('equipment:filter_keywords_reference')


@login_required
def filter_keyword_toggle(request, pk):
    """Переключение активности ключевого слова."""
    kw = get_object_or_404(FilterKeyword, pk=pk)
    kw.is_active = not kw.is_active
    kw.save()
    status = 'активировано' if kw.is_active else 'деактивировано'
    messages.success(request, f'Ключевое слово "{kw.keyword}" {status}')
    return redirect('equipment:filter_keywords_reference')
