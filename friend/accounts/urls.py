from rest_framework.routers import DefaultRouter
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import (
    DepartmentViewSet, PositionViewSet, UserViewSet,
    InternalGroupViewSet, GroupMappingViewSet, ADSyncSettingsViewSet,
    ADGroupSyncView,
)
from .views import (
    HomeView, UserListView, DepartmentListView, DashboardView,
    PositionListView, archive_user, restore_user,
    UserGeneralView, UserTrainingsView, UserEquipmentView, UserAccessView,
    UserEditView, UserNotifySettingsView, UserEditContactsView, UserEditAdditionalView,
    UserClearMaxIdView, UserClearTelegramIdView, UserResetPasswordView,
    InternalGroupListView, InternalGroupCreateView, InternalGroupUpdateView, InternalGroupDeleteView,
    InternalGroupDetailView, InternalGroupAddUserView, InternalGroupRemoveUserView,
    InternalGroupSearchUsersView,
    GroupMappingListView, GroupMappingCreateView, GroupMappingUpdateView, GroupMappingDeleteView,
    MenuSettingsView,
)
from .views import LoginView, LogoutView

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'positions', PositionViewSet)
router.register(r'users', UserViewSet)
router.register(r'internal-groups', InternalGroupViewSet, basename='internal-group')
router.register(r'group-mappings', GroupMappingViewSet, basename='group-mapping')
router.register(r'ad-sync-settings', ADSyncSettingsViewSet, basename='ad-sync-settings')
router.register(r'ad-sync', ADGroupSyncView, basename='ad-sync')

app_name = 'accounts'

urlpatterns = [
    # Авторизация
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='accounts:login'), name='logout'),

    # API
    path('api/', include(router.urls)),

    # Основные страницы
    path('', DashboardView.as_view(), name='dashboard'),
    path('home/', HomeView.as_view(), name='home'),
    path('users/', UserListView.as_view(), name='user_list'),
    # Профиль пользователя
    path('users/<int:pk>/general/', UserGeneralView.as_view(), name='user_general'),
    path('users/<int:pk>/reset-password/', UserResetPasswordView.as_view(), name='user_reset_password'),
    path('users/<int:pk>/clear_max_id/', UserClearMaxIdView.as_view(), name='user_clear_max_id'),
    path('users/<int:pk>/clear_telegram_id/', UserClearTelegramIdView.as_view(), name='user_clear_telegram_id'),
    path('users/<int:pk>/edit_contacts/', UserEditContactsView.as_view(), name='user_edit_contacts'),
    path('users/<int:pk>/edit_additional/', UserEditAdditionalView.as_view(), name='user_edit_additional'),
    path('users/<int:pk>/notify_settings/', UserNotifySettingsView.as_view(), name='user_notify_settings'),
    path('users/<int:pk>/trainings/', UserTrainingsView.as_view(), name='user_trainings'),
    path('users/<int:pk>/equipment/', UserEquipmentView.as_view(), name='user_equipment'),
    path('users/<int:pk>/access/', UserAccessView.as_view(), name='user_access'),
    # Редактирование
    path('users/<int:pk>/edit/', UserEditView.as_view(), name='user_edit'),
    path('departments/', DepartmentListView.as_view(), name='department_list'),
    path('positions/', PositionListView.as_view(), name='position_list'),
    # Архивирование/восстановление
    path('users/<int:pk>/archive/', archive_user, name='archive_user'),
    path('users/<int:pk>/restore/', restore_user, name='restore_user'),

    # Внутренние группы и AD-синхронизация
    path('internal-groups/', InternalGroupListView.as_view(), name='internal_group_list'),
    path('internal-groups/<int:pk>/', InternalGroupDetailView.as_view(), name='internal_group_detail'),
    path('internal-groups/create/', InternalGroupCreateView.as_view(), name='internal_group_create'),
    path('internal-groups/<int:pk>/edit/', InternalGroupUpdateView.as_view(), name='internal_group_edit'),
    path('internal-groups/<int:pk>/delete/', InternalGroupDeleteView.as_view(), name='internal_group_delete'),
    path('internal-groups/<int:pk>/add-user/', InternalGroupAddUserView.as_view(), name='internal_group_add_user'),
    path('internal-groups/<int:pk>/remove-user/', InternalGroupRemoveUserView.as_view(), name='internal_group_remove_user'),
    path('internal-groups/search-users/', InternalGroupSearchUsersView.as_view(), name='internal_group_search_users'),
    path('group-mappings/', GroupMappingListView.as_view(), name='group_mapping_list'),
    path('group-mappings/create/', GroupMappingCreateView.as_view(), name='group_mapping_create'),
    path('group-mappings/<int:pk>/edit/', GroupMappingUpdateView.as_view(), name='group_mapping_edit'),
    path('group-mappings/<int:pk>/delete/', GroupMappingDeleteView.as_view(), name='group_mapping_delete'),
    
    # Настройка меню
    path('menu-settings/', MenuSettingsView.as_view(), name='menu_settings'),
]
