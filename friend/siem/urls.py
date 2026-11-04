from django.urls import path
from . import views

app_name = 'siem'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('hosts/', views.hosts_list, name='hosts'),
    path('hosts/<int:pk>/', views.host_detail, name='host_detail'),
    path('events/', views.events_list, name='events'),
    path('events/<int:pk>/', views.event_detail, name='event_detail'),
    path('report/security/', views.report_security, name='report_security'),
    path('report/inventory/', views.report_inventory, name='report_inventory'),
    path('report/inventory/<int:pk>/', views.inventory_host_history, name='inventory_host_history'),
    path('report/inventory/<int:pk>/packages/', views.inventory_packages, name='inventory_packages'),
    path('report/hosts/', views.report_hosts, name='report_hosts'),
    # Управление отсутствиями
    path('leaves/', views.leaves_list, name='leaves_list'),
    path('leaves/create/', views.leave_create, name='leave_create'),
    path('leaves/<int:pk>/', views.leave_detail, name='leave_detail'),
    path('leaves/<int:pk>/edit/', views.leave_edit, name='leave_edit'),
    path('leaves/<int:pk>/delete/', views.leave_delete, name='leave_delete'),
    # Алерты отсутствия
    path('alerts/', views.alerts_list, name='alerts_list'),
    path('alerts/<int:pk>/ack/', views.alert_acknowledge, name='alert_ack'),
    # История входов
    path('logins/', views.login_history_list, name='login_history'),
    path('logins/<int:pk>/', views.login_history_detail, name='login_history_detail'),
    # Журнал блокировок экрана
    path('screen-locks/', views.screen_lock_log_list, name='screen_lock_log'),
    # Справка
    path('help/', views.help_page, name='help'),
]
