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

    # Справочник исключений
    path('exclude-keywords/', views.exclude_keywords_reference, name='exclude_keywords_reference'),
    path('exclude-keywords/add/', views.exclude_keyword_add, name='exclude_keyword_add'),
    path('exclude-keywords/<int:pk>/edit/', views.exclude_keyword_edit, name='exclude_keyword_edit'),
    path('exclude-keywords/<int:pk>/delete/', views.exclude_keyword_delete, name='exclude_keyword_delete'),
    path('exclude-keywords/<int:pk>/toggle/', views.exclude_keyword_toggle, name='exclude_keyword_toggle'),

    # Справочник ключевых слов фильтрации
    path('filter-keywords/', views.filter_keywords_reference, name='filter_keywords_reference'),
    path('filter-keywords/add/', views.filter_keyword_add, name='filter_keyword_add'),
    path('filter-keywords/<int:pk>/edit/', views.filter_keyword_edit, name='filter_keyword_edit'),
    path('filter-keywords/<int:pk>/delete/', views.filter_keyword_delete, name='filter_keyword_delete'),
    path('filter-keywords/<int:pk>/toggle/', views.filter_keyword_toggle, name='filter_keyword_toggle'),

    # Настройки полей
    path('field-settings/', views.field_settings, name='field_settings'),

    # Оборудование подразделения
    path('department/<int:department_id>/', views.department_equipment, name='department_equipment'),

    # Загрузка основных средств
    path('upload-os/', views.upload_os_csv, name='upload_os'),
    path('upload-os/download-new/', views.download_new_items, name='download_new_items'),
    path('upload-os/import-new/', views.import_new_items_to_db, name='import_new_items_to_db'),

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
    path('inventory/assigned/', views.assigned_equipment, name='assigned_equipment'),
    path('inventory/search/', views.inventory_search, name='inventory_search'),

    # Справочник расположения
    path('locations/', views.location_list, name='location_list'),
    # Город
    path('locations/city/add/', views.location_city_add, name='location_city_add'),
    path('locations/city/<int:pk>/edit/', views.location_city_edit, name='location_city_edit'),
    path('locations/city/<int:pk>/delete/', views.location_city_delete, name='location_city_delete'),
    # Корпус
    path('locations/building/add/', views.location_building_add, name='location_building_add'),
    path('locations/building/<int:pk>/edit/', views.location_building_edit, name='location_building_edit'),
    path('locations/building/<int:pk>/delete/', views.location_building_delete, name='location_building_delete'),
    # Этаж
    path('locations/floor/add/', views.location_floor_add, name='location_floor_add'),
    path('locations/floor/<int:pk>/edit/', views.location_floor_edit, name='location_floor_edit'),
    path('locations/floor/<int:pk>/delete/', views.location_floor_delete, name='location_floor_delete'),
    # Кабинет
    path('locations/room/add/', views.location_room_add, name='location_room_add'),
    path('locations/room/<int:pk>/edit/', views.location_room_edit, name='location_room_edit'),
    path('locations/room/<int:pk>/delete/', views.location_room_delete, name='location_room_delete'),
    # API
    path('locations/api/floors/', views.get_floors_ajax, name='get_floors_ajax'),
    # Категории оборудования (AJAX)
    path('api/categories/', views.get_categories_ajax, name='get_categories_ajax'),
    path('api/subcategories/', views.get_subcategories_ajax, name='get_subcategories_ajax'),

    # CRUD справочник категорий
    path('categories/manage/', views.category_list, name='category_list'),
    path('categories/manage/add/', views.category_add, name='category_add'),
    path('categories/manage/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/manage/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('categories/manage/<int:pk>/restore/', views.category_restore, name='category_restore'),

    # Старые URL для совместимости
    path('computers/', views.ComputerListView.as_view(), name='computers'),
    path('computers/type/<str:equipment_type>/', views.ComputerListView.as_view(), name='computers_type'),

    # Альтернативные URL для типов оборудования
    path('printers/', views.EquipmentListView.as_view(equipment_type='printer'), name='printers'),
    path('medical/', views.EquipmentListView.as_view(equipment_type='medical'), name='medical'),
    path('peripherals/', views.EquipmentListView.as_view(equipment_type='peripheral'), name='peripherals'),
    path('phones/', views.EquipmentListView.as_view(equipment_type='phone'), name='phones'),
    path('vks/', views.EquipmentListView.as_view(equipment_type='vks'), name='vks'),

    # Оборудование по категории (динамическое)
    path('category/<slug:category_slug>/', views.category_equipment_list, name='category_equipment'),
]
