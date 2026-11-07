from django import forms
from django.contrib.auth import get_user_model
from .models import TrainingType, Training, TrainingEnrollment
from accounts.models import Department

User = get_user_model()


class TrainingTypeForm(forms.ModelForm):
    """Форма для создания/редактирования типа обучения."""

    class Meta:
        model = TrainingType
        fields = ['name', 'description', 'skillspace_course_id', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Охрана труда',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание типа обучения...',
            }),
            'skillspace_course_id': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID курса на Skillspace',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class TrainingForm(forms.ModelForm):
    """Форма для создания/редактирования назначения обучения."""

    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True, is_fired=False)
        .order_by('last_name', 'first_name'),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'data-placeholder': 'Выберите сотрудников...',
            'data-live-search': 'true',
        }),
        required=True,
        label='Сотрудники',
    )

    class Meta:
        model = Training
        fields = ['title', 'description', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название обучения',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание обучения...',
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
        }

    def __init__(self, *args, **kwargs):
        training_type = kwargs.pop('training_type', None)
        super().__init__(*args, **kwargs)
        if training_type:
            self.fields['training_type'] = forms.HiddenInput()
            # Filter users by department if needed
            self.fields['users'].queryset = User.objects.filter(
                is_active=True, is_fired=False
            ).order_by('last_name', 'first_name')


class TrainingEnrollmentFormSet(forms.BaseInlineFormSet):
    """FormSet для управления назначениями обучения."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.fields['status'].widget = forms.Select(choices=TrainingEnrollment.Status.choices, attrs={'class': 'form-select'})


class TrainingUserSelectionForm(forms.Form):
    """Форма для выбора сотрудников при создании обучения."""

    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True).order_by('name'),
        required=False,
        label='Подразделение',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True, is_fired=False)
        .order_by('last_name', 'first_name'),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
        }),
        required=True,
        label='Сотрудники',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.data.get('department'):
            dept_id = self.data.get('department')
            self.fields['users'].queryset = User.objects.filter(
                is_active=True, is_fired=False, department_id=dept_id
            ).order_by('last_name', 'first_name')
        elif not self.data:
            # Default: all active users
            self.fields['users'].queryset = User.objects.filter(
                is_active=True, is_fired=False
            ).order_by('last_name', 'first_name')
