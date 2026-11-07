from django import forms
from django.contrib.auth import get_user_model
from .models import Message

User = get_user_model()


class MessageForm(forms.ModelForm):
    """Форма создания/редактирования сообщения."""
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label='Получатели (личные сообщения)',
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
    )
    department = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label='Или рассылка по подразделению',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Загружаем активных пользователей
        self.fields['recipients'].queryset = User.objects.filter(
            archive_status=User.STATUS_ACTIVE
        ).select_related('department').order_by('last_name', 'first_name')
        # Загружаем активные подразделения
        from accounts.models import Department
        self.fields['department'].queryset = Department.objects.filter(
            is_active=True
        ).order_by('name')

    class Meta:
        model = Message
        fields = ['title', 'content', 'priority', 'channel', 'department']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Заголовок (необязательно)'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Текст сообщения...'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'channel': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        recipients = cleaned_data.get('recipients')
        department = cleaned_data.get('department')
        if not recipients and not department:
            raise forms.ValidationError('Укажите получателей или подразделение для рассылки.')
        return cleaned_data


class MessageFilterForm(forms.Form):
    """Фильтр для списка сообщений."""
    status = forms.ChoiceField(
        choices=[('', 'Все статусы')] + Message.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    channel = forms.ChoiceField(
        choices=[('', 'Все каналы')] + Message.CHANNEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    priority = forms.ChoiceField(
        choices=[('', 'Все приоритеты')] + Message.PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    search = forms.CharField(
        required=False,
        label='Поиск',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Заголовок или содержание...'}),
    )
