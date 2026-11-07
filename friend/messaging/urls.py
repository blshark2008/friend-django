from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    path('', views.MessageListView.as_view(), name='message_list'),
    path('new/', views.MessageCreateView.as_view(), name='message_create'),
    path('<int:pk>/', views.MessageDetailView.as_view(), name='message_detail'),
    path('<int:pk>/edit/', views.MessageUpdateView.as_view(), name='message_edit'),
    path('<int:pk>/delete/', views.MessageDeleteView.as_view(), name='message_delete'),
    path('<int:pk>/send/', views.send_message, name='message_send'),
    path('stats/', views.MessageStatsView.as_view(), name='message_stats'),
    path('users/<int:pk>/send/', views.SendMessageToUserView.as_view(), name='message_send_to_user'),
]
