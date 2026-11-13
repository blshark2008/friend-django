from django.urls import path
from . import views

app_name = 'logging_app'

urlpatterns = [
    # Веб-интерфейс журнала
    path('logs/', views.LogListView.as_view(), name='log_list'),
]
