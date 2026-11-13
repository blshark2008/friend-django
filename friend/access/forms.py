from django import forms
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q
from .models import (
    Resource, AccessGroup, AccessGrant, AccessRequest, Role, RoleGroup,
    NetworkResourceDetail, SoftwareResourceDetail, RemoteAccessDetail,
    ServerResourceDetail, DatabaseResourceDetail, ApplicationResourceDetail,
    StorageResourceDetail, CloudResourceDetail, HardwareResourceDetail,
)

User = get_user_model()


class ResourceForm(forms.ModelForm):
    """Форма для ресурса."""

    class Meta:
        model = Resource
        fields = [
            'name', 'type', 'description', 'owner', 'is_active', 'last_audit_date',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'owner': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'last_audit_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class NetworkDetailForm(forms.ModelForm):
    """Форма для сетевого ресурса."""
    class Meta:
        model = NetworkResourceDetail
        fields = ['host', 'port', 'protocol', 'share_path']
        widgets = {
            'host': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'protocol': forms.TextInput(attrs={'class': 'form-control'}),
            'share_path': forms.TextInput(attrs={'class': 'form-control'}),
        }


class SoftwareDetailForm(forms.ModelForm):
    """Форма для программного ресурса."""
    class Meta:
        model = SoftwareResourceDetail
        fields = ['vendor', 'version', 'license_count', 'license_key']
        widgets = {
            'vendor': forms.TextInput(attrs={'class': 'form-control'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'license_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'license_key': forms.TextInput(attrs={'class': 'form-control'}),
        }


class RemoteAccessDetailForm(forms.ModelForm):
    """Форма для удалённого доступа."""
    class Meta:
        model = RemoteAccessDetail
        fields = ['gateway', 'protocol', 'port']
        widgets = {
            'gateway': forms.TextInput(attrs={'class': 'form-control'}),
            'protocol': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ServerDetailForm(forms.ModelForm):
    """Форма для сервера."""
    class Meta:
        model = ServerResourceDetail
        fields = ['hostname', 'os_type', 'ssh_port', 'ip_address']
        widgets = {
            'hostname': forms.TextInput(attrs={'class': 'form-control'}),
            'os_type': forms.TextInput(attrs={'class': 'form-control'}),
            'ssh_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control'}),
        }


class DatabaseDetailForm(forms.ModelForm):
    """Форма для базы данных."""
    class Meta:
        model = DatabaseResourceDetail
        fields = ['host', 'port', 'database_name', 'engine']
        widgets = {
            'host': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'database_name': forms.TextInput(attrs={'class': 'form-control'}),
            'engine': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ApplicationDetailForm(forms.ModelForm):
    """Форма для приложения."""
    class Meta:
        model = ApplicationResourceDetail
        fields = ['url', 'environment', 'api_endpoint']
        widgets = {
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'environment': forms.TextInput(attrs={'class': 'form-control'}),
            'api_endpoint': forms.TextInput(attrs={'class': 'form-control'}),
        }


class StorageDetailForm(forms.ModelForm):
    """Форма для хранилища."""
    class Meta:
        model = StorageResourceDetail
        fields = ['capacity_gb', 'used_gb', 'mount_point', 'filesystem']
        widgets = {
            'capacity_gb': forms.NumberInput(attrs={'class': 'form-control'}),
            'used_gb': forms.NumberInput(attrs={'class': 'form-control'}),
            'mount_point': forms.TextInput(attrs={'class': 'form-control'}),
            'filesystem': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CloudDetailForm(forms.ModelForm):
    """Форма для облачного ресурса."""
    class Meta:
        model = CloudResourceDetail
        fields = ['provider', 'region', 'account_id']
        widgets = {
            'provider': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'account_id': forms.TextInput(attrs={'class': 'form-control'}),
        }


class HardwareDetailForm(forms.ModelForm):
    """Форма для оборудования."""
    class Meta:
        model = HardwareResourceDetail
        fields = ['serial_number', 'model', 'location']
        widgets = {
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
        }


class AccessGroupForm(forms.ModelForm):
    """Форма для группы доступа.

    Наименование конструируется автоматически по компонентам:
    <ТИП>-<РЕСУРС>-<ОБЛАСТЬ>-<УРОВЕНЬ>
    """

    class Meta:
        model = AccessGroup
        fields = [
            'type_prefix', 'resource_name', 'area', 'access_level',
            'old_name', 'description', 'is_active', 'audited',
            'resource', 'pinned_department', 'ad_group_dn', 'ad_sync_enabled',
        ]
        widgets = {
            'type_prefix': forms.Select(attrs={'class': 'form-select'}),
            'resource_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: samba-share-01'}),
            'area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: office-msk, lab-2'}),
            'access_level': forms.Select(attrs={'class': 'form-select'}),
            'old_name': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'audited': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'resource': forms.Select(attrs={'class': 'form-select'}),
            'pinned_department': forms.Select(attrs={'class': 'form-select'}),
            'ad_group_dn': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Фильтруем ресурсы: показываем только те, к которым ещё не привязаны группы
        attached_resource_ids = AccessGroup.objects.filter(
            resource__isnull=False, is_active=True
        ).values_list('resource_id', flat=True)
        
        if self.instance and self.instance.pk:
            # При редактировании — показываем текущий ресурс + свободные
            current_resource_id = self.instance.resource_id
            self.fields['resource'].queryset = Resource.objects.filter(
                models.Q(pk=current_resource_id) | ~models.Q(pk__in=attached_resource_ids)
            ).distinct()
        else:
            # При создании — только свободные ресурсы
            self.fields['resource'].queryset = Resource.objects.filter(
                ~models.Q(pk__in=attached_resource_ids)
            )

        # Для существующей группы — распаковываем имя на компоненты
        if self.instance and self.instance.pk:
            parsed = self.instance.parse_name()
            if parsed.get('type_prefix') in AccessGroup.TYPE_PREFIXES:
                self.initial['type_prefix'] = parsed['type_prefix']
            self.initial['resource_name'] = parsed.get('resource_name', '')
            self.initial['area'] = parsed.get('area', '')
            self.initial['access_level'] = parsed.get('access_level', '')
            # Старое имя — текущее name, если оно не сгенерировано
            if not self.instance.old_name and self.instance.name:
                self.initial['old_name'] = self.instance.name

        # Динамически заполняем уровни доступа по выбранному типу
        self._update_level_choices()

    def _update_level_choices(self):
        """Обновляет выбор уровней доступа на основе выбранного типа."""
        prefix = self.data.get('type_prefix', '') or self.initial.get('type_prefix', '')
        if prefix in AccessGroup.TYPE_PREFIXES:
            levels = AccessGroup.TYPE_PREFIXES[prefix]['levels']
            self.fields['access_level'].choices = [(l, l) for l in levels]
        else:
            self.fields['access_level'].choices = []

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Генерируем name из компонентов
        instance.name = instance.generate_name()
        # Устанавливаем дату аудита при отметке
        if instance.audited and not instance.audited_at:
            from django.utils import timezone
            instance.audited_at = timezone.now()
        if commit:
            instance.save()
        return instance


class AccessGrantForm(forms.ModelForm):
    """Форма для гранта доступа."""

    class Meta:
        model = AccessGrant
        fields = ['grant_type', 'user', 'group', 'level', 'expires_at', 'justification']
        widgets = {
            'grant_type': forms.Select(attrs={'class': 'form-select'}),
            'user': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'expires_at': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'justification': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].required = False
        self.fields['group'].required = False


class AccessRequestForm(forms.ModelForm):
    """Форма для заявки на доступ."""

    class Meta:
        model = AccessRequest
        fields = ['resource', 'level', 'justification']
        widgets = {
            'resource': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'justification': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class RoleForm(forms.ModelForm):
    """Форма для роли."""

    class Meta:
        model = Role
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RoleGroupForm(forms.ModelForm):
    """Форма для добавления группы в роль."""
    class Meta:
        model = RoleGroup
        fields = ['access_group']
        widgets = {
            'access_group': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        role = kwargs.pop('role', None)
        super().__init__(*args, **kwargs)
        if role:
            # Показываем все группы, исключая уже добавленные в эту роль
            existing_ids = role.groups.values_list('access_group_id', flat=True)
            self.fields['access_group'].queryset = AccessGroup.objects.filter(
                ~models.Q(pk__in=existing_ids)
            )
