from django import forms
from django.contrib.auth import get_user_model
from .models import (
    Equipment, EquipmentAssignment,
    EQUIPMENT_CATEGORIES, EQUIPMENT_SUBTYPES,
    get_subtypes_for_category,
)

User = get_user_model()


class EquipmentForm(forms.ModelForm):
    """Основная форма для создания/редактирования оборудования."""

    class Meta:
        model = Equipment
        fields = [
            'inventory_number', 'serial_number', 'name', 'brand', 'model',
            'category', 'subtype',
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
            'is_active', 'archived',
        ]
        widgets = {
            'inventory_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Инв. номер'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Заводской номер'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Бренд'}),
            'model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Модель'}),
            'category': forms.Select(attrs={'class': 'form-select', 'id': 'id_category'}),
            'subtype': forms.Select(attrs={'class': 'form-select', 'id': 'id_subtype'}),
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем начальные подтипы на основе категории
        if self.instance and self.instance.pk:
            initial_subtype = self.instance.subtype
        else:
            initial_subtype = 'desktop'
        self.fields['subtype'].choices = get_subtypes_for_category(
            self.initial.get('category', 'computer') or initial_subtype
        )


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
