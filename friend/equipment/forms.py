from django import forms
from django.contrib.auth import get_user_model
from .models import (
    Equipment, EquipmentAssignment,
    EquipmentCategory,
    City, Building, Floor, Room,
    EquipmentMovement, EquipmentRepair, EquipmentUpgrade,
    EquipmentDecommissionRecord,
)

User = get_user_model()


class EquipmentForm(forms.ModelForm):
    """Основная форма для создания/редактирования оборудования."""

    class Meta:
        model = Equipment
        fields = [
            'inventory_number', 'serial_number', 'name', 'brand', 'model',
            'category', 'subcategory',
            'assigned_user', 'responsible_user',
            'hostname', 'mac_address', 'ip_address',
            'cpu', 'ram_gb', 'storage_gb',
            'os', 'os_version',
            'antivirus_engine', 'antivirus_active',
            'screen_size', 'resolution',
            'printer_status',
            'camera_count',
            'phone_number', 'extension',
            'calibration_date', 'next_calibration',
            'status',
            'location', 'place',
            # Бухгалтерская информация
            'acquisition_date', 'acquisition_cost', 'initial_number',
            'useful_life_months', 'depreciation_method',
            # Информация о списании
            'decommission_date', 'decommission_act', 'decommission_notes',
            'is_active', 'archived',
        ]
        widgets = {
            'inventory_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Инв. номер'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Заводской номер'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Бренд'}),
            'model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Модель'}),
            'category': forms.Select(attrs={'class': 'form-select', 'id': 'id_category'}),
            'subcategory': forms.Select(attrs={'class': 'form-select', 'id': 'id_subcategory'}),
            'assigned_user': forms.Select(attrs={'class': 'form-select'}),
            'responsible_user': forms.Select(attrs={'class': 'form-select'}),
            'hostname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя в сети (hostname)'}),
            'mac_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MAC: AA:BB:CC:DD:EE:FF'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IP-адрес'}),
            'cpu': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Процессор'}),
            'ram_gb': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'ОЗУ (ГБ)'}),
            'storage_gb': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Диск (ГБ)'}),
            'os': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ОС'}),
            'os_version': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Версия ОС'}),
            'antivirus_engine': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Антивирус'}),
            'antivirus_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'screen_size': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Диагональ (например: 15.6")'}),
            'resolution': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Разрешение (например: 1920x1080)'}),
            'printer_status': forms.Select(attrs={'class': 'form-select'}),
            'camera_count': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Кол-во камер'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Внешний номер'}),
            'extension': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Внутренний номер'}),
            'calibration_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_calibration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Кабинет'}),
            'place': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Место'}),
            # Бухгалтерская информация
            'acquisition_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'acquisition_cost': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Стоимость (₽)'}),
            'initial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Первоначальная стоимость'}),
            'useful_life_months': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Срок (мес.)'}),
            'depreciation_method': forms.Select(attrs={'class': 'form-select'}),
            # Информация о списании
            'decommission_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'decommission_act': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Акт (№, дата)'}),
            'decommission_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Причина, основание'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем начальные подкатегории на основе категории
        if self.instance and self.instance.pk:
            initial_subcategory = self.instance.subcategory
        else:
            initial_subcategory = None
        self.fields['subcategory'].initial = initial_subcategory


class SimpleEquipmentForm(forms.ModelForm):
    """Упрощённая форма: только инвентарный номер, серийный номер, расположение."""

    class Meta:
        model = Equipment
        fields = ['inventory_number', 'serial_number', 'location', 'place']
        widgets = {
            'inventory_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Инв. номер'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Заводской номер'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Кабинет'}),
            'place': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Место'}),
        }


class AssignUserForm(forms.Form):
    """Форма назначения пользователя на оборудование."""
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        label='Пользователь',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    lookup_by_serial = forms.CharField(
        required=False,
        label='Или введите серийный номер для поиска в SIEM',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Серийный номер из SIEM',
            'id': 'serial_lookup_input',
        }),
    )


# ============================================================================
# Формы справочника расположения
# ============================================================================

class CityForm(forms.ModelForm):
    """Форма для создания/редактирования города."""

    class Meta:
        model = City
        fields = ['name', 'code', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название города'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Код (необязательно)'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BuildingForm(forms.ModelForm):
    """Форма для создания/редактирования корпуса."""

    class Meta:
        model = Building
        fields = ['city', 'name', 'code', 'address', 'is_active']
        widgets = {
            'city': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название корпуса'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Код (необязательно)'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Адрес корпуса'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FloorForm(forms.ModelForm):
    """Форма для создания/редактирования этажа."""

    class Meta:
        model = Floor
        fields = ['building', 'floor_number', 'rooms_count', 'is_active']
        widgets = {
            'building': forms.Select(attrs={'class': 'form-select'}),
            'floor_number': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Номер этажа'}),
            'rooms_count': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Кол-во кабинетов'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RoomForm(forms.ModelForm):
    """Форма для создания/редактирования кабинета."""

    class Meta:
        model = Room
        fields = ['building', 'floor', 'room_number', 'capacity', 'is_active']
        widgets = {
            'building': forms.Select(attrs={'class': 'form-select', 'id': 'id_room_building'}),
            'floor': forms.Select(attrs={'class': 'form-select', 'id': 'id_room_floor'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Номер кабинета'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Вместимость'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ============================================================================
# Формы справочника категорий оборудования
# ============================================================================

class EquipmentCategoryForm(forms.ModelForm):
    """Форма для создания/редактирования категории оборудования."""

    class Meta:
        model = EquipmentCategory
        fields = ['name', 'parent', 'code_1c', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название категории'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'code_1c': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Код 1С (необязательно)'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ============================================================================
# Формы истории оборудования
# ============================================================================

class EquipmentMovementForm(forms.ModelForm):
    """Форма для записи перемещения оборудования."""

    class Meta:
        model = EquipmentMovement
        fields = [
            'equipment', 'from_location', 'to_location',
            'from_room', 'to_room',
            'from_user', 'to_user', 'move_date', 'notes',
        ]
        widgets = {
            'equipment': forms.Select(attrs={'class': 'form-select'}),
            'from_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Предыдущее расположение'}),
            'to_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Новое расположение'}),
            'from_room': forms.Select(attrs={'class': 'form-select'}),
            'to_room': forms.Select(attrs={'class': 'form-select'}),
            'from_user': forms.Select(attrs={'class': 'form-select'}),
            'to_user': forms.Select(attrs={'class': 'form-select'}),
            'move_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Примечания'}),
        }


class EquipmentRepairForm(forms.ModelForm):
    """Форма для записи ремонта оборудования."""

    class Meta:
        model = EquipmentRepair
        fields = [
            'equipment', 'repair_type', 'description', 'result',
            'service_company', 'warranty_number', 'cost',
            'start_date', 'end_date', 'responsible_user',
        ]
        widgets = {
            'equipment': forms.Select(attrs={'class': 'form-select'}),
            'repair_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Описание неисправности/работ'}),
            'result': forms.Select(attrs={'class': 'form-select'}),
            'service_company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Сервисная компания'}),
            'warranty_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Номер гарантии'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Стоимость (₽)'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'responsible_user': forms.Select(attrs={'class': 'form-select'}),
        }


class EquipmentUpgradeForm(forms.ModelForm):
    """Форма для записи модернизации оборудования."""

    class Meta:
        model = EquipmentUpgrade
        fields = [
            'equipment', 'description', 'old_specs', 'new_specs',
            'result', 'cost', 'performed_date', 'performed_by',
            'responsible_user',
        ]
        widgets = {
            'equipment': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Описание модернизации'}),
            'old_specs': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Было (характеристики)'}),
            'new_specs': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Стало (характеристики)'}),
            'result': forms.Select(attrs={'class': 'form-select'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Стоимость (₽)'}),
            'performed_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'performed_by': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Выполнено кем'}),
            'responsible_user': forms.Select(attrs={'class': 'form-select'}),
        }


class EquipmentDecommissionRecordForm(forms.ModelForm):
    """Форма для записи о списании оборудования."""

    class Meta:
        model = EquipmentDecommissionRecord
        fields = [
            'equipment', 'act_number', 'act_date', 'reason',
            'commission', 'notes',
        ]
        widgets = {
            'equipment': forms.Select(attrs={'class': 'form-select'}),
            'act_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Номер акта'}),
            'act_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Причина списания'}),
            'commission': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Состав комиссии (ФИО)'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Примечания'}),
        }
