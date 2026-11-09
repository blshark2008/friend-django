from django import forms
from django.contrib.auth import get_user_model
from .models import Message

User = get_user_model()


class MessageForm(forms.ModelForm):
    """Форма создания/редактирования сообщения."""

    class Meta:
        model = Message
        fields = ['title', 'content', 'priority']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Заголовок (необязательно)'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Текст сообщения...'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }


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
