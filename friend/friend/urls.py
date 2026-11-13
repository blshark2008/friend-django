"""
URL configuration for friend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
    Function views
        1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
    Class-based views
        1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
    Including another URLconf
        1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework.routers import DefaultRouter
from siem import views as siem_views
from messaging.views import max_webhook, api_max_webhook
from logging_app.views import api_log_event

router = DefaultRouter()
router.register(r'api/siem/ingest', siem_views.IngestViewSet, basename='ingest')
router.register(r'api/siem/ingest/inventory', siem_views.InventoryIngestViewSet, basename='inventory')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('equipment/', include('equipment.urls')),
    path('siem/', include('siem.urls')),
    path('training/', include('training.urls')),
    path('messaging/', include('messaging.urls', namespace='messaging')),
    path('scenarios/', include('scenarios.urls', namespace='scenarios')),
    path('access/', include('access.urls', namespace='access')),
    path('logging/', include('logging_app.urls', namespace='logging_app')),
    # MAX Bot webhook
    path('max/webhook/', max_webhook, name='max_webhook'),
    # API для webhook relay
    path('api/max/webhook/', api_max_webhook, name='api_max_webhook'),
    # API для приёма событий журнала
    path('api/logging/event/', api_log_event, name='api_log_event'),
]

# API-маршруты для агентов
urlpatterns += router.urls

# Обслуживание статических файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else None)
