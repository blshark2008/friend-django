from django import template

register = template.Library()


@register.filter
def class_name(obj):
    """Возвращает имя класса объекта."""
    return obj.__class__.__name__


@register.filter
def get(d, key):
    """Получение элемента из словаря по ключу: dict|get:key"""
    if d is None or not isinstance(d, dict):
        return None
    return d.get(key)


@register.filter
def get_default(d, key):
    """Получение элемента из словаря по ключу с значением по умолчанию 0."""
    if d is None or not isinstance(d, dict):
        return 0
    return d.get(key, 0)
