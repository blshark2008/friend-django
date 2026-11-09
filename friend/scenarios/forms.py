import json
from django import forms
from .models import (
    Category, Scenario, Branch, Step,
    Run, Role, EmployeeRole,
    ScenarioMailGroup,
)


# ============================================================================
# Кастомный виджет для JSON-полей
# ============================================================================

class FlexibleJSONTextarea(forms.Textarea):
    """Виджет, который преобразует () в [] перед валидацией."""

    def __init__(self, *args, **kwargs):
        kwargs['attrs'] = kwargs.get('attrs', {})
        kwargs['attrs']['class'] = 'form-control'
        super().__init__(*args, **kwargs)

    def value_from_datadict(self, data, files, name):
        value = data.get(name, '')
        if value is not None:
            value = str(value).strip()
            # () → [] (пустой список)
            if value == '()':
                value = '[]'
            # {} → {} (пустой объект)
            elif value == '{}':
                value = '{}'
        return value

    def format_value(self, value):
        """Конвертирует Python-объект в JSON-строку для виджета."""
        if value is None:
            return '{}'
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return super().format_value(value)


class FlexibleJSONField(forms.JSONField):
    """JSON-поле с поддержкой () как пустого списка."""

    def __init__(self, *args, **kwargs):
        kwargs['widget'] = FlexibleJSONTextarea
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip()
            if value == '()':
                return []
            if value == '{}':
                return {}
            if value == '':
                return None
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                raise forms.ValidationError('Невалидный JSON')
        return super().to_python(value)


# ============================================================================
# Формы справочников
# ============================================================================

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ScenarioForm(forms.ModelForm):
    class Meta:
        model = Scenario
        fields = ['category', 'name', 'description', 'is_active']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['scenario', 'name']
        widgets = {
            'scenario': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class StepForm(forms.ModelForm):
    # Переопределяем JSON-поля для гибкой валидации
    # () и [] считаются заполненными; пустое поле — обязательное
    message_json = FlexibleJSONField(required=False, label='JSON сбора ответа')
    mailing_list_json = FlexibleJSONField(required=False, label='JSON списка рассылки')
    exclusion_list_json = FlexibleJSONField(required=False, label='JSON исключений')
    db_write_json = FlexibleJSONField(required=False, label='JSON записи в базу')
    escalate_to_json = FlexibleJSONField(required=False, label='JSON эскалации')

    class Meta:
        model = Step
        fields = [
            'branch', 'prev_result_code',
            'message_text', 'message_json',
            'mailing_list_json', 'exclusion_list_json',
            'db_write_json', 'deadline_min', 'escalate_to_json',
        ]
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'prev_result_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EVAC_YES, etc.'}),
            'message_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Текст с переменными {corpus}, {user.name}...'}),
            'message_json': FlexibleJSONTextarea(),
            'mailing_list_json': FlexibleJSONTextarea(),
            'exclusion_list_json': FlexibleJSONTextarea(),
            'db_write_json': FlexibleJSONTextarea(),
            'deadline_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'escalate_to_json': FlexibleJSONTextarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Только message_text — обязательное поле
        self.fields['message_text'].required = True
        # Остальные поля — необязательные, заполнятся значениями по умолчанию
        for field_name in self.fields:
            if field_name != 'message_text':
                self.fields[field_name].required = False

        # Для нового шага — устанавливаем пустой JSON по умолчанию
        if not self.instance or not self.instance.pk:
            self.fields['message_json'].initial = '{}'

    def clean(self):
        cleaned_data = super().clean()

        # JSON-поля: пустая строка → пустой объект/список
        json_fields_dict = ['message_json', 'mailing_list_json', 'exclusion_list_json',
                            'db_write_json', 'escalate_to_json']
        json_fields_list = ['mailing_list_json', 'exclusion_list_json']
        for field in json_fields_dict:
            value = cleaned_data.get(field)
            if value is None or value == '':
                if field in json_fields_list:
                    cleaned_data[field] = []
                else:
                    cleaned_data[field] = {}

        # deadline_min: пустое → 0
        if not cleaned_data.get('deadline_min'):
            cleaned_data['deadline_min'] = 0

        return cleaned_data


class RunStartForm(forms.Form):
    """Форма запуска сценария с параметрами."""
    # Динамически добавляем поля в зависимости от сценария
    def __init__(self, *args, scenario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.scenario = scenario

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


# ============================================================================
# Формы для редактора (AJAX)
# ============================================================================

class ScenarioEditorForm(forms.Form):
    """Форма для сохранения структуры сценария через JSON."""
    branches_json = forms.CharField(
        required=True,
        widget=forms.HiddenInput(),
        help_text='JSON со структурой веток и шагов',
    )


# ============================================================================
# Формы для групп рассылки сценариев
# ============================================================================

class ScenarioMailGroupForm(forms.ModelForm):
    """Форма для групп рассылки сценариев."""

    class Meta:
        model = ScenarioMailGroup
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: Руководители отделений'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Описание группы...'}),
        }
