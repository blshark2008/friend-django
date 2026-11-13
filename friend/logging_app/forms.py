from django import forms
from .models import LogEntry


class LogEntryFilterForm(forms.Form):
    """Форма фильтрации журнала."""
    q = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Поиск...'}),
    )
    source = forms.ChoiceField(
        choices=[('', 'Все источники')] + LogEntry.objects.values_list('source', 'source').distinct(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    action = forms.ChoiceField(
        choices=[('')] + LogEntry.Action.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    severity = forms.ChoiceField(
        choices=[('')] + LogEntry.Severity.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
    )
