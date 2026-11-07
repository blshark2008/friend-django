# Training app URLs

from django.urls import path
from . import views

app_name = 'training'

urlpatterns = [
    # Training types
    path('', views.training_list, name='list'),
    path('types/', views.training_type_list, name='type_list'),
    path('types/create/', views.training_type_create, name='type_create'),
    path('types/<int:pk>/edit/', views.training_type_edit, name='type_edit'),
    path('types/<int:pk>/delete/', views.training_type_delete, name='type_delete'),

    # Trainings (instances)
    path('types/<int:type_pk>/trainings/', views.training_list_by_type, name='type_trainings'),
    path('types/<int:type_pk>/trainings/create/', views.training_create, name='training_create'),
    path('trainings/<int:pk>/', views.training_detail, name='training_detail'),
    path('trainings/<int:pk>/edit/', views.training_edit, name='training_edit'),
    path('trainings/<int:pk>/delete/', views.training_delete, name='training_delete'),
    path('trainings/<int:pk>/sync/', views.training_sync, name='training_sync'),
    path('trainings/<int:pk>/sync-webhook/', views.training_webhook, name='training_webhook'),

    # Sync all
    path('sync-all/', views.sync_all_trainings, name='sync_all'),

    # Reports
    path('reports/', views.training_report, name='report'),
]
