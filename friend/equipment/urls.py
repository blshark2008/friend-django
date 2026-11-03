from django.urls import path
from . import views

app_name = 'equipment'

urlpatterns = [
    # Общий список
    path('', views.equipment_list, name='equipment_list'),
    path('type/<str:equipment_type>/', views.EquipmentListView.as_view(), name='list_by_type'),
    path('export/', views.export_equipment_to_excel, name='export_excel'),

    # Дашборд
    path('dashboard/', views.dashboard, name='dashboard'),

    # Справочник категорий
    path('categories/', views.categories_reference, name='categories_reference'),

    # Настройки полей
    path('field-settings/', views.field_settings, name='field_settings'),

    # Оборудование подразделения
    path('department/<int:department_id>/', views.department_equipment, name='department_equipment'),

    # Загрузка основных средств
    path('upload-os/', views.upload_os_csv, name='upload_os'),

    # CRUD
    path('add/<str:equipment_type>/', views.equipment_add, name='add'),
    path('edit/<str:equipment_type>/<int:pk>/', views.equipment_edit, name='edit'),
    path('archive/<str:equipment_type>/<int:pk>/', views.equipment_archive, name='archive'),

    # Назначение пользователя
    path('assign/', views.assign_user_generic, name='assign'),
    path('assign/<str:equipment_type>/<int:pk>/', views.assign_user, name='assign_detail'),
    path('assign-ajax/<str:equipment_type>/<int:pk>/', views.change_assigned_user_ajax, name='assign_ajax'),
    path('clear-assign/<str:equipment_type>/<int:pk>/', views.clear_assigned_user, name='clear_assign'),
    path('lookup-user/', views.lookup_user_by_serial, name='lookup_user'),
    path('search-users/', views.search_users_ajax, name='search_users'),
    path('quick-assign-users/', views.quick_assign_users, name='quick_assign_users'),

    # Детальная информация
    path('detail/<str:equipment_type>/<int:pk>/', views.equipment_detail, name='detail'),
    path('update-siem/<str:equipment_type>/<int:pk>/', views.update_from_siem, name='update_siem'),
    path('siem-host/<str:serial>/', views.redirect_to_siem_host, name='siem_host_redirect'),

    # Перемещение оборудования
    path('move/<int:pk>/', views.move_equipment, name='move'),

    # Массовые операции
    path('batch-archive/', views.batch_archive, name='batch_archive'),
    path('batch-move/', views.batch_move, name='batch_move'),

    # Закрепление МОЛ
    path('assign-mol/<str:equipment_type>/<int:pk>/', views.assign_mol, name='assign_mol'),
    path('assign-mol-ajax/<str:equipment_type>/<int:pk>/', views.assign_mol_ajax, name='assign_mol_ajax'),
    path('assign-mol-ajax-old/<str:equipment_type>/<int:pk>/', views.change_responsible_user_ajax, name='assign_mol_ajax_old'),
    path('clear-mol/<str:equipment_type>/<int:pk>/', views.clear_responsible_user, name='clear_mol'),
    path('assign-mol/batch/', views.assign_mol_batch, name='assign_mol_batch'),

    # Инвентаризация
    path('inventory/', views.equipment_inventory, name='inventory'),
    path('inventory/<str:equipment_type>/<int:pk>/', views.equipment_inventory_detail, name='inventory_detail'),

    # Старые URL для совместимости
    path('computers/', views.ComputerListView.as_view(), name='computers'),
    path('computers/type/<str:equipment_type>/', views.ComputerListView.as_view(), name='computers_type'),

    # Альтернативные URL для типов оборудования
    path('printers/', views.EquipmentListView.as_view(equipment_type='printer'), name='printers'),
    path('medical/', views.EquipmentListView.as_view(equipment_type='medical'), name='medical'),
    path('peripherals/', views.EquipmentListView.as_view(equipment_type='peripheral'), name='peripherals'),
    path('phones/', views.EquipmentListView.as_view(equipment_type='phone'), name='phones'),
    path('vks/', views.EquipmentListView.as_view(equipment_type='vks'), name='vks'),
]
