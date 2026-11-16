from django.urls import path
from . import views

app_name = 'access'

urlpatterns = [
    # API
    path('api/groups/search/', views.api_search_groups, name='api_search_groups'),
    path('api/roles/<int:role_pk>/groups/search/', views.api_search_groups_for_role, name='api_search_groups_for_role'),
    path('api/containers/search/', views.api_search_containers, name='api_search_containers'),
    path('api/users/search/', views.api_search_users, name='api_search_users'),
    path('api/external-users/search/', views.api_search_external_users, name='api_search_external_users'),

    # Ресурсы
    path('resources/', views.ResourceListView.as_view(), name='resource_list'),
    path('resources/new/', views.ResourceCreateView.as_view(), name='resource_create'),
    path('resources/<int:pk>/', views.ResourceDetailView.as_view(), name='resource_detail'),
    path('resources/<int:pk>/edit/', views.ResourceUpdateView.as_view(), name='resource_edit'),
    path('resources/<int:pk>/delete/', views.ResourceDeleteView.as_view(), name='resource_delete'),
    path('resources/<int:resource_pk>/groups/<int:group_id>/detach/', views.ResourceDetachGroupView.as_view(), name='resource_detach_group'),
    path('resources/<int:resource_pk>/groups/attach/', views.ResourceAttachGroupView.as_view(), name='resource_attach_group'),

    # Группы доступа
    path('groups/', views.AccessGroupListView.as_view(), name='group_list'),
    path('groups/export-csv/', views.AccessGroupExportCsvView.as_view(), name='group_export_csv'),
    path('groups/new/', views.AccessGroupCreateView.as_view(), name='group_create'),
    path('groups/<int:pk>/', views.AccessGroupDetailView.as_view(), name='group_detail'),
    path('groups/<int:pk>/edit/', views.AccessGroupUpdateView.as_view(), name='group_edit'),
    path('groups/<int:pk>/delete/', views.AccessGroupDeleteView.as_view(), name='group_delete'),
    path('groups/<int:pk>/restore/', views.AccessGroupRestoreView.as_view(), name='group_restore'),

    # Гранты доступа
    path('grants/', views.GrantListView.as_view(), name='grant_list'),
    path('grants/export/', views.GrantExportCsvView.as_view(), name='grant_export'),
    path('grants/new/', views.GrantCreateView.as_view(), name='grant_create'),
    path('grants/<int:pk>/', views.GrantDetailView.as_view(), name='grant_detail'),
    path('grants/<int:pk>/delete/', views.GrantDeleteView.as_view(), name='grant_delete'),
    path('grants/<int:pk>/restore/', views.GrantRestoreView.as_view(), name='grant_restore'),
    path('grants/import/', views.GrantImportView.as_view(), name='grant_import'),

    # Гранты внешних лиц
    path('grants/external/', views.ExternalGrantListView.as_view(), name='external_grant_list'),
    path('grants/external/export/', views.ExternalGrantExportCsvView.as_view(), name='external_grant_export'),
    path('grants/external/new/', views.ExternalGrantCreateView.as_view(), name='external_grant_create'),
    path('grants/external/<int:pk>/delete/', views.ExternalGrantDeleteView.as_view(), name='external_grant_delete'),
    path('grants/external/<int:pk>/restore/', views.ExternalGrantRestoreView.as_view(), name='external_grant_restore'),

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
    path('roles/<int:pk>/containers/add/', views.RoleGroupContainerAddView.as_view(), name='role_container_add'),
    path('roles/<int:role_pk>/containers/<int:container_id>/delete/', views.RoleGroupContainerDeleteView.as_view(), name='role_container_delete'),

    # Контейнеры групп доступа
    path('containers/', views.GroupContainerListView.as_view(), name='container_list'),
    path('containers/new/', views.GroupContainerCreateView.as_view(), name='container_create'),
    path('containers/<int:pk>/', views.GroupContainerDetailView.as_view(), name='container_detail'),
    path('containers/<int:pk>/edit/', views.GroupContainerUpdateView.as_view(), name='container_edit'),
    path('containers/<int:pk>/delete/', views.GroupContainerDeleteView.as_view(), name='container_delete'),
    path('containers/<int:pk>/restore/', views.GroupContainerRestoreView.as_view(), name='container_restore'),
    path('containers/<int:container_pk>/groups/<int:group_id>/delete/', views.GroupContainerGroupDeleteView.as_view(), name='container_group_delete'),
    path('containers/<int:pk>/groups/add/', views.GroupContainerGroupAddView.as_view(), name='container_group_add'),

    # Привязка ролей к должностям
    path('positions/roles/', views.PositionRoleListView.as_view(), name='position_roles'),
    path('positions/roles/export/', views.PositionRoleExportCsvView.as_view(), name='position_roles_export'),
    path('positions/roles/<int:pk>/add/', views.PositionRoleAddView.as_view(), name='position_role_add'),
    path('positions/roles/<int:pk>/delete/', views.PositionRoleDeleteView.as_view(), name='position_role_delete'),

    # Аудит доступа
    path('audit/', views.AccessAuditView.as_view(), name='audit'),
    path('audit/export/', views.AccessAuditExportView.as_view(), name='audit_export'),
    path('audit/export-not-found/', views.AccessAuditNotFoundExportView.as_view(), name='audit_export_not_found'),

    # Подрядчики — Организации
    path('contractors/organizations/', views.OrganizationListView.as_view(), name='organization_list'),
    path('contractors/organizations/new/', views.OrganizationCreateView.as_view(), name='organization_create'),
    path('contractors/organizations/<int:pk>/', views.OrganizationDetailView.as_view(), name='organization_detail'),
    path('contractors/organizations/<int:pk>/edit/', views.OrganizationUpdateView.as_view(), name='organization_edit'),
    path('contractors/organizations/<int:pk>/delete/', views.OrganizationDeleteView.as_view(), name='organization_delete'),

    # Подрядчики — Договоры
    path('contractors/contracts/', views.ContractListView.as_view(), name='contract_list'),
    path('contractors/contracts/new/', views.ContractCreateView.as_view(), name='contract_create'),
    path('contractors/contracts/<int:pk>/', views.ContractDetailView.as_view(), name='contract_detail'),
    path('contractors/contracts/<int:pk>/edit/', views.ContractUpdateView.as_view(), name='contract_edit'),
    path('contractors/contracts/<int:pk>/delete/', views.ContractDeleteView.as_view(), name='contract_delete'),

    # Подрядчики — Внешние лица
    path('contractors/external-users/', views.ExternalUserListView.as_view(), name='external_user_list'),
    path('contractors/external-users/new/', views.ExternalUserCreateView.as_view(), name='external_user_create'),
    path('contractors/external-users/<int:pk>/', views.ExternalUserDetailView.as_view(), name='external_user_detail'),
    path('contractors/external-users/<int:pk>/edit/', views.ExternalUserUpdateView.as_view(), name='external_user_edit'),
    path('contractors/external-users/<int:pk>/delete/', views.ExternalUserDeleteView.as_view(), name='external_user_delete'),
    path('contractors/external-users/import/', views.ExternalUserImportView.as_view(), name='external_user_import'),
]
