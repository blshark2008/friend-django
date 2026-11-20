from django import forms
import logging
from django.contrib.auth import get_user_model
from .models import TrainingType, Training, TrainingEnrollment, TrainingCategory, SkillspaceGroup
from accounts.models import Department

User = get_user_model()
logger = logging.getLogger(__name__)


class TrainingCategoryForm(forms.ModelForm):
    """Форма для создания/редактирования категории обучения."""

    class Meta:
        model = TrainingCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Информационная безопасность',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание категории...',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class TrainingTypeForm(forms.ModelForm):
    """Форма для создания/редактирования типа обучения."""

    skillspace_course = forms.ChoiceField(
        required=False,
        label='Курс на Skillspace',
        help_text='Выберите курс из справочника',
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
    )

    class Meta:
        model = TrainingType
        fields = ['category', 'name', 'description', 'is_active']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Охрана труда',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание типа обучения...',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load courses from Skillspace API
        courses = []
        try:
            from training.services.skillspace_api import SkillspaceClient, SkillspaceAPIError
            client = SkillspaceClient()
            api_courses = client.get_course_list()
            courses = [('', '— Не выбран —')] + [
                (c['id'], f"{c['name']} ({c['id']})")
                for c in api_courses
            ]
        except Exception as e:
            logger.error(f'Failed to load courses: {e}')
            courses = [('', '— Ошибка загрузки —')]
        
        self.fields['skillspace_course'].choices = courses
        
        # Set initial value from instance
        if self.instance and self.instance.pk:
            current_id = self.instance.skillspace_course_id
            if current_id:
                self.fields['skillspace_course'].initial = current_id

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.skillspace_course_id = self.cleaned_data.get('skillspace_course', '')
        if commit:
            instance.save()
        return instance


class TrainingForm(forms.ModelForm):
    """Форма для создания/редактирования назначения обучения."""

    class Meta:
        model = Training
        fields = ['title', 'description', 'start_date', 'end_date', 'training_type']
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
            'training_type': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        training_type = None
        if self.instance and self.instance.pk:
            training_type = self.instance.training_type

        # Get training_type from initial/data if not on instance
        if not training_type:
            tt_id = self.data.get('training_type') or self.initial.get('training_type')
            if tt_id:
                try:
                    training_type = TrainingType.objects.get(pk=tt_id)
                except TrainingType.DoesNotExist:
                    pass

        # Always create group field
        groups = SkillspaceGroup.objects.none()
        if training_type:
            groups = SkillspaceGroup.objects.filter(course=training_type)

        self.fields['group'] = forms.ModelChoiceField(
            queryset=groups,
            required=False,
            label='Группа на Skillspace',
            help_text='Выберите группу из справочника',
            widget=forms.Select(attrs={
                'class': 'form-select',
            }),
        )
        # Set initial value
        if self.instance and self.instance.pk and self.instance.group:
            self.fields['group'].initial = self.instance.group

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Explicitly save group from cleaned_data
        group = self.cleaned_data.get('group')
        if group is not None:
            instance.group = group
        elif self.instance and self.instance.pk:
            # Preserve existing group when editing and field not changed
            instance.group = self.instance.group

        if commit:
            instance.save()
        return instance


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


