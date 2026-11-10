from django.urls import path
from . import views

app_name = 'scenarios'

urlpatterns = [
    # Категории
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/new/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),

    # Сценарии
    path('', views.ScenarioListView.as_view(), name='scenario_list'),
    path('new/', views.ScenarioCreateView.as_view(), name='scenario_create'),
    path('<int:pk>/edit/', views.ScenarioUpdateView.as_view(), name='scenario_edit'),
    path('<int:pk>/delete/', views.ScenarioDeleteView.as_view(), name='scenario_delete'),
    path('<int:pk>/editor/', views.ScenarioEditorView.as_view(), name='scenario_editor'),
    path('<int:pk>/start/', views.ScenarioStartView.as_view(), name='scenario_start'),

    # Ветки
    path('branches/new/', views.BranchCreateView.as_view(), name='branch_create'),
    path('branches/<int:pk>/edit/', views.BranchUpdateView.as_view(), name='branch_edit'),
    path('branches/<int:pk>/delete/', views.BranchDeleteView.as_view(), name='branch_delete'),

    # Шаги
    path('steps/new/', views.StepCreateView.as_view(), name='step_create'),
    path('steps/<int:pk>/edit/', views.StepUpdateView.as_view(), name='step_edit'),
    path('steps/<int:pk>/delete/', views.StepDeleteView.as_view(), name='step_delete'),

    # Запуски
    path('runs/', views.RunListView.as_view(), name='run_list'),
    path('runs/<int:pk>/', views.RunDetailView.as_view(), name='run_detail'),
    path('runs/<int:pk>/start/', views.RunStartView.as_view(), name='run_start'),
    path('runs/<int:pk>/cancel/', views.RunCancelView.as_view(), name='run_cancel'),
    path('runs/<int:pk>/abort/', views.run_abort_view, name='run_abort'),
    path('runs/<int:pk>/cancel-run/', views.run_cancel_action_view, name='run_cancel_action'),
    path('runs/bulk-delete/', views.run_bulk_delete, name='run_bulk_delete'),

    # Журнал
    path('journal/', views.JournalListView.as_view(), name='journal_list'),

    # Роли
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/new/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    path('roles/<int:pk>/edit/', views.RoleUpdateView.as_view(), name='role_edit'),
    path('roles/<int:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),
    path('roles/<int:pk>/add_user/', views.RoleAddUserView.as_view(), name='role_add_user'),
    path('roles/<int:pk>/remove_user/', views.RoleRemoveUserView.as_view(), name='role_remove_user'),

    # API для бота
    path('api/answer/', views.process_bot_answer, name='api_answer'),

    # API для выбора result_code
    path('api/available-codes/', views.available_result_codes, name='api_available_codes'),

    # API для виджета списка рассылки
    path('api/roles/', views.mailing_list_roles, name='api_mailing_list_roles'),
    path('api/mail-groups/', views.mailing_list_mail_groups, name='api_mailing_list_mail_groups'),

    # Группы рассылки сценариев
    path('mail-groups/', views.ScenarioMailGroupListView.as_view(), name='mail_group_list'),
    path('mail-groups/new/', views.ScenarioMailGroupCreateView.as_view(), name='mail_group_create'),
    path('mail-groups/<int:pk>/', views.ScenarioMailGroupDetailView.as_view(), name='mail_group_detail'),
    path('mail-groups/<int:pk>/edit/', views.ScenarioMailGroupUpdateView.as_view(), name='mail_group_edit'),
    path('mail-groups/<int:pk>/delete/', views.ScenarioMailGroupDeleteView.as_view(), name='mail_group_delete'),
    path('mail-groups/<int:pk>/add_user/', views.ScenarioMailGroupAddUserView.as_view(), name='mail_group_add_user'),
    path('mail-groups/<int:pk>/remove_user/', views.ScenarioMailGroupRemoveUserView.as_view(), name='mail_group_remove_user'),
    path('mail-groups/<int:pk>/add_dept/', views.ScenarioMailGroupAddDeptView.as_view(), name='mail_group_add_dept'),
    path('mail-groups/<int:pk>/remove_dept/', views.ScenarioMailGroupRemoveDeptView.as_view(), name='mail_group_remove_dept'),

    # Настройка обработки ответов
    path('<int:pk>/answer-config/', views.AnswerConfigView.as_view(), name='answer_config'),
    path('api/answer-config-add/', views.answer_config_add, name='api_answer_config_add'),
    path('api/answer-config-delete/', views.answer_config_delete, name='api_answer_config_delete'),
    path('api/answer-config-update/', views.answer_config_update, name='api_answer_config_update'),

    # API для сводных данных
    path('runs/<int:pk>/summary/', views.run_summary_api, name='run_summary_api'),

    # API для сохранения сообщений
    path('api/save-messages/', views.save_scenario_messages, name='api_save_messages'),
]
