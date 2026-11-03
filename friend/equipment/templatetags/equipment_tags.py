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
