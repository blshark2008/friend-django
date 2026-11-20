from urllib.parse import urlparse

from .models import MenuSection, MenuItem, InternalGroup


def back_url(request):
    """Добавляет URL предыдущей страницы в контекст каждого шаблона."""
    referrer = request.META.get('HTTP_REFERER', '')
    if referrer and '://' in referrer:
        ref_domain = urlparse(referrer).netloc
        req_domain = request.get_host()
        if ref_domain != req_domain:
            referrer = ''
    return {'back_url': referrer}


def menu_items(request):
    """Добавляет видимые пункты меню в контекст каждого шаблона."""
    if not request.user.is_authenticated:
        return {'visible_menu_items': []}
    
    # Получаем все активные пункты меню, отсортированные по разделу
    items = MenuItem.objects.filter(
        is_active=True
    ).select_related('section').order_by(
        'section__order', 'section__name', 'order', 'name'
    )
    
    # Если пользователь суперпользователь или staff — показываем всё
    if request.user.is_superuser or request.user.is_staff:
        return {'visible_menu_items': items}
    
    # Получаем внутренние группы пользователя
    user_groups = request.user.internal_groups.all()
    
    # Фильтруем пункты меню по внутренним группам
    # Пункт меню виден, если код раздела совпадает с кодом группы пользователя
    visible_items = []
    for item in items:
        # Ищем группу с таким же кодом, как у раздела
        group = user_groups.filter(code=item.section.code).first()
        if group:
            visible_items.append(item)
    
    return {'visible_menu_items': visible_items}
