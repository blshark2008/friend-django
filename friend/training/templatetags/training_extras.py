from django import template

register = template.Library()


@register.filter
def sum_field(queryset, field_path):
    """
    Sums a field across a queryset.
    Usage: {{ queryset|sum_field:"field_name" }}
    """
    if not queryset:
        return 0
    try:
        return sum(getattr(obj, field_path, 0) for obj in queryset)
    except (AttributeError, TypeError):
        return 0


@register.filter
def choices_dict(text_choices):
    """
    Returns the first choice from a TextChoices class.
    Usage: {{ model.Status|choices_dict }}
    """
    try:
        return text_choices.choices[0] if text_choices.choices else ('', '')
    except (AttributeError, IndexError):
        return ('', '')
