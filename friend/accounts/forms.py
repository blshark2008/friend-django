from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import User, InternalGroup, GroupMapping


class LoginForm(AuthenticationForm):
    """Форма авторизации."""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Логин',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Пароль',
        })
    )


class UserEditForm(forms.ModelForm):
    """Форма редактирования пользователя."""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'patronymic',
            'corporate_phone', 'personal_phone', 'snils',
            'corporate_email', 'personal_email',
            'department', 'position', 'employee_code_1c',
            'tab_number', 'domain_account',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'patronymic': forms.TextInput(attrs={'class': 'form-control'}),
            'corporate_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'personal_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'snils': forms.TextInput(attrs={'class': 'form-control'}),
            'corporate_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'personal_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'employee_code_1c': forms.TextInput(attrs={'class': 'form-control'}),
            'tab_number': forms.TextInput(attrs={'class': 'form-control'}),
            'domain_account': forms.TextInput(attrs={'class': 'form-control'}),
        }


class InternalGroupForm(forms.ModelForm):
    """Форма для создания/редактирования внутренней группы."""
    class Meta:
        model = InternalGroup
        fields = ['name', 'code', 'description', 'is_active', 'is_system']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название группы'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'technical-code-here'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Описание группы'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_system': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class GroupMappingForm(forms.ModelForm):
    """Форма для создания/редактирования связки AD-группы."""
    internal_group = forms.ModelChoiceField(
        queryset=InternalGroup.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Внутренняя группа',
    )

    class Meta:
        model = GroupMapping
        fields = ['ad_group_name', 'ad_group_dn', 'internal_group', 'is_active']
        widgets = {
            'ad_group_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: FG_APP_READ'}),
            'ad_group_dn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CN=FG_APP_READ,OU=Groups,DC=domain,DC=local'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
