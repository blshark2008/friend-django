from django.urls import path
from . import views

app_name = 'access'

urlpatterns = [
    # API
    path('api/groups/search/', views.api_search_groups, name='api_search_groups'),
    path('api/roles/<int:role_pk>/groups/search/', views.api_search_groups_for_role, name='api_search_groups_for_role'),

    # Ресурсы
    path('resources/', views.ResourceListView.as_view(), name='resource_list'),
    path('resources/new/', views.ResourceCreateView.as_view(), name='resource_create'),
    path('resources/<int:pk>/', views.ResourceDetailView.as_view(), name='resource_detail'),
    path('resources/<int:pk>/edit/', views.ResourceUpdateView.as_view(), name='resource_edit'),
    path('resources/<int:pk>/delete/', views.ResourceDeleteView.as_view(), name='resource_delete'),

    # Группы доступа
    path('groups/', views.AccessGroupListView.as_view(), name='group_list'),
    path('groups/new/', views.AccessGroupCreateView.as_view(), name='group_create'),
    path('groups/<int:pk>/', views.AccessGroupDetailView.as_view(), name='group_detail'),
    path('groups/<int:pk>/edit/', views.AccessGroupUpdateView.as_view(), name='group_edit'),
    path('groups/<int:pk>/delete/', views.AccessGroupDeleteView.as_view(), name='group_delete'),
    path('groups/<int:pk>/restore/', views.AccessGroupRestoreView.as_view(), name='group_restore'),

    # Гранты доступа
    path('grants/', views.GrantListView.as_view(), name='grant_list'),
    path('grants/new/', views.GrantCreateView.as_view(), name='grant_create'),
    path('grants/<int:pk>/delete/', views.GrantDeleteView.as_view(), name='grant_delete'),

    # Заявки на доступ
    path('requests/', views.AccessRequestListView.as_view(), name='request_list'),
    path('requests/new/', views.AccessRequestCreateView.as_view(), name='request_create'),
    path('requests/<int:pk>/', views.AccessRequestDetailView.as_view(), name='request_detail'),
    path('requests/<int:pk>/edit/', views.AccessRequestUpdateView.as_view(), name='request_edit'),

    # Роли
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/new/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    path('roles/<int:pk>/edit/', views.RoleUpdateView.as_view(), name='role_edit'),
    path('roles/<int:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),
    path('roles/<int:pk>/restore/', views.RoleRestoreView.as_view(), name='role_restore'),
    path('roles/<int:pk>/groups/add/', views.RoleGroupAddView.as_view(), name='role_group_add'),
    path('roles/<int:role_pk>/groups/<int:group_id>/delete/', views.RoleGroupDeleteView.as_view(), name='role_group_delete'),
]
