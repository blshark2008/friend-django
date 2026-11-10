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
    # Поиск
    path('search/users/', views.search_users, name='search_users'),
    path('search/departments/', views.search_departments, name='search_departments'),
    path('search/mail-groups/', views.search_mail_groups, name='search_mail_groups'),
    # Группы рассылки
#     path('groups/', views.MailGroupListView.as_view(), name='mail_group_list'),
#     path('groups/new/', views.MailGroupCreateView.as_view(), name='mail_group_create'),
#     path('groups/<int:pk>/', views.MailGroupDetailView.as_view(), name='mail_group_detail'),
#     path('groups/<int:pk>/edit/', views.MailGroupUpdateView.as_view(), name='mail_group_edit'),
#     path('groups/<int:pk>/delete/', views.MailGroupDeleteView.as_view(), name='mail_group_delete'),
#     path('groups/<int:pk>/add_user/', views.MailGroupAddUserView.as_view(), name='mail_group_add_user'),
#     path('groups/<int:pk>/remove_user/', views.MailGroupRemoveUserView.as_view(), name='mail_group_remove_user'),
#     path('groups/<int:pk>/add_dept/', views.MailGroupAddDeptView.as_view(), name='mail_group_add_dept'),
#     path('groups/<int:pk>/remove_dept/', views.MailGroupRemoveDeptView.as_view(), name='mail_group_remove_dept'),
]
