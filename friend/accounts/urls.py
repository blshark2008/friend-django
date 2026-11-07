from rest_framework.routers import DefaultRouter
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import DepartmentViewSet, PositionViewSet
from .views import (
    HomeView, UserListView, DepartmentListView, DashboardView,
    PositionListView, archive_user, restore_user,
    UserGeneralView, UserTrainingsView, UserEquipmentView, UserAccessView,
    UserEditView, UserNotifySettingsView, UserEditContactsView, UserEditAdditionalView,
    UserClearMaxIdView, UserClearTelegramIdView,
)
from .views import LoginView, LogoutView

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'positions', PositionViewSet)

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
]
