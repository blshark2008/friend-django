# Training app URLs

from django.urls import path
from . import views

app_name = 'training'

urlpatterns = [
    # Training types
    path('', views.training_list, name='list'),
    path('types/', views.training_type_list, name='type_list'),
    path('types/courses/', views.training_course_list, name='type_courses'),
    path('types/courses/<str:course_id>/toggle/', views.training_course_toggle, name='course_toggle'),
    path('types/create/', views.training_type_create, name='type_create'),

    # Training categories
    path('categories/', views.training_category_list, name='category_list'),
    path('categories/create/', views.training_category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.training_category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.training_category_delete, name='category_delete'),
    path('types/<int:pk>/edit/', views.training_type_edit, name='type_edit'),
    path('types/<int:pk>/delete/', views.training_type_delete, name='type_delete'),

    # Trainings (instances)
    path('types/<int:type_pk>/trainings/', views.training_list_by_type, name='type_trainings'),
    path('types/<int:type_pk>/trainings/create/', views.training_create, name='training_create'),
    path('trainings/<int:pk>/', views.training_detail, name='training_detail'),
    path('trainings/<int:pk>/edit/', views.training_edit, name='training_edit'),
    path('trainings/<int:pk>/delete/', views.training_delete, name='training_delete'),
    path('trainings/<int:pk>/sync/', views.training_sync, name='training_sync'),
    path('trainings/<int:pk>/sync-status/', views.training_sync_status, name='training_sync_status'),
    path('webhook/', views.training_webhook, name='training_webhook'),
    path('trainings/<int:pk>/add-user/', views.training_add_user, name='training_add_user'),
    path('trainings/<int:pk>/assign-course/<int:user_id>/', views.training_assign_course, name='training_assign_course'),
    path('trainings/<int:pk>/add-users-by-departments/', views.training_add_users_by_departments, name='training_add_users_by_departments'),
    path('search-users/', views.search_users, name='search_users'),
    path('search-departments/', views.search_departments, name='search_departments'),
    path('trainings/<int:pk>/remove-user/<int:user_id>/', views.training_remove_user, name='training_remove_user'),
    path('trainings/<int:pk>/bulk-remove/', views.training_bulk_remove, name='training_bulk_remove'),
    path('trainings/<int:pk>/check-progress/', views.training_check_progress, name='training_check_progress'),
    path('trainings/<int:pk>/invite-link/', views.training_invite_link, name='training_invite_link'),

    # Sync all
    path('sync-all/', views.sync_all_trainings, name='sync_all'),

    # Reports
    path('reports/', views.training_report, name='report'),
]
