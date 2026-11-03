from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User, Department, Position


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Логин')
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)


class UserEditForm(forms.ModelForm):
    """Форма редактирования профиля пользователя."""

    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        label='Подразделение',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'style': 'max-width: 100%;',
        }),
    )
    position = forms.ModelChoiceField(
        queryset=Position.objects.filter(is_active=True),
        required=False,
        label='Должность',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'style': 'max-width: 100%;',
        }),
    )

    class Meta:
        model = User
        fields = [
            'last_name', 'first_name', 'patronymic',
            'tab_number', 'username',
            'department', 'position',
            'corporate_email', 'personal_email',
            'corporate_phone', 'personal_phone',
            'snils', 'domain_account',
            'hire_date', 'fire_date',
            'is_mol', 'is_admin',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'patronymic': forms.TextInput(attrs={'class': 'form-control'}),
            'tab_number': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'corporate_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'personal_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'corporate_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'personal_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'snils': forms.TextInput(attrs={'class': 'form-control'}),
            'domain_account': forms.TextInput(attrs={'class': 'form-control'}),
            'hire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_mol': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_admin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
