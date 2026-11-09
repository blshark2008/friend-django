from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.views.generic.edit import FormMixin
from django.db.models import Q, Count, Max, Prefetch
from django.http import JsonResponse
import json

from .models import (
    Category, Scenario, Branch, Step,
    Run, StepRun, Answer, DbValue, Log,
    Role, EmployeeRole,
    ScenarioMailGroup,
)
from .forms import (
    CategoryForm, ScenarioForm, BranchForm, StepForm,
    RunStartForm, ScenarioEditorForm,
    ScenarioMailGroupForm,
)
from .services.executor import ScenarioExecutor
from accounts.models import User, Department


# ============================================================================
# Категории
# ============================================================================

class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'scenarios/category_list.html'
    context_object_name = 'categories'


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'scenarios/category_form.html'
    success_url = reverse_lazy('scenarios:category_list')


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'scenarios/category_form.html'
    success_url = reverse_lazy('scenarios:category_list')


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    success_url = reverse_lazy('scenarios:category_list')


# ============================================================================
# Сценарии — список
# ============================================================================

class ScenarioListView(LoginRequiredMixin, ListView):
    model = Scenario
    template_name = 'scenarios/scenario_list.html'
    context_object_name = 'scenarios'
    paginate_by = 20

    def get_queryset(self):
        qs = Scenario.objects.select_related('category').prefetch_related('branches')
        category_id = self.request.GET.get('category')
        if category_id:
            qs = qs.filter(category_id=category_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True)
        context['total_branches'] = Branch.objects.count()
        return context


# ============================================================================
# Запуск сценария
# ============================================================================

class ScenarioStartView(LoginRequiredMixin, View):
    """Запуск сценария — создаёт Run и запускает executor."""

    def post(self, request, *args, **kwargs):
        scenario_id = kwargs.get('pk')
        scenario = get_object_or_404(Scenario, pk=scenario_id)

        run = Run.objects.create(
            scenario=scenario,
            started_by=request.user,
            params_json={},
            status=Run.STATUS_PENDING,
        )

        executor = ScenarioExecutor(run)
        executor.start()

        messages.success(request, f'Сценарий «{scenario.name}» запущен.')
        return redirect('scenarios:run_detail', pk=run.pk)


# ============================================================================
# Сценарии — редактор (табличный)
# ============================================================================

class ScenarioEditorView(LoginRequiredMixin, DetailView):
    """Табличный редактор сценария с ветками и шагами."""
    model = Scenario
    template_name = 'scenarios/scenario_editor.html'
    context_object_name = 'scenario'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['branches'] = self.object.branches.all().prefetch_related('steps')
        context['categories'] = Category.objects.filter(is_active=True)
        context['roles'] = Role.objects.filter(is_active=True)
        return context


class ScenarioCreateView(LoginRequiredMixin, CreateView):
    model = Scenario
    form_class = ScenarioForm
    template_name = 'scenarios/scenario_form.html'

    def get_success_url(self):
        return reverse('scenarios:scenario_editor', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Сценарий создан.')
        return response


class ScenarioUpdateView(LoginRequiredMixin, UpdateView):
    model = Scenario
    form_class = ScenarioForm
    template_name = 'scenarios/scenario_form.html'

    def get_success_url(self):
        return reverse('scenarios:scenario_editor', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Сценарий обновлён.')
        return response


class ScenarioDeleteView(LoginRequiredMixin, DeleteView):
    model = Scenario
    success_url = reverse_lazy('scenarios:scenario_list')


# ============================================================================
# Ветки
# ============================================================================

class BranchCreateView(LoginRequiredMixin, CreateView):
    model = Branch
    form_class = BranchForm
    template_name = 'scenarios/branch_form.html'

    def get_success_url(self):
        return reverse('scenarios:scenario_editor', kwargs={'pk': self.object.scenario_id})

    def get_initial(self):
        initial = super().get_initial()
        scenario_id = self.request.GET.get('scenario')
        if scenario_id:
            initial['scenario'] = scenario_id
        return initial

    def form_valid(self, form):
        import uuid
        # Генерируем уникальный код из UUID (первые 8 символов)
        code = uuid.uuid4().hex[:8].upper()
        form.instance.code = code
        response = super().form_valid(form)
        messages.success(self.request, 'Ветка создана.')
        return response


class BranchUpdateView(LoginRequiredMixin, UpdateView):
    model = Branch
    form_class = BranchForm
    template_name = 'scenarios/branch_form.html'

    def get_success_url(self):
        return reverse('scenarios:scenario_editor', kwargs={'pk': self.object.scenario_id})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Ветка обновлена.')
        return response


class BranchDeleteView(LoginRequiredMixin, DeleteView):
    model = Branch

    def get_success_url(self):
        return reverse('scenarios:scenario_editor', kwargs={'pk': self.object.scenario_id})

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Ветка удалена.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# Шаги
# ============================================================================

class StepCreateView(LoginRequiredMixin, CreateView):
    model = Step
    form_class = StepForm
    template_name = 'scenarios/step_form.html'

    def get_success_url(self):
        return reverse('scenarios:scenario_editor', kwargs={'pk': self.object.branch.scenario_id})

    def get_initial(self):
        initial = super().get_initial()
        branch_id = self.request.GET.get('branch')
        if branch_id:
            initial['branch'] = branch_id
        return initial

    def form_valid(self, form):
        # Автоматически проставляем step_order: макс + 1 для ветки
        branch = form.cleaned_data.get('branch')
        if branch:
            max_order = Step.objects.filter(branch=branch).aggregate(Max('step_order'))['step_order__max']
            form.instance.step_order = (max_order or 0) + 1

        self.object = form.save()
        messages.success(self.request, 'Шаг создан.')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mailing_list_data'] = self._get_mailing_list_data()
        return context

    def _get_mailing_list_data(self):
        """Собирает все данные для виджетов списка рассылки и исключений."""
        from accounts.models import Department
        from scenarios.models import ScenarioMailGroup, Role

        # Сотрудники
        users = []
        for u in User.objects.filter(archive_status=User.STATUS_ACTIVE).select_related('department'):
            users.append({
                'id': u.pk,
                'tab_number': u.tab_number,
                'last_name': u.last_name,
                'first_name': u.first_name,
                'patronymic': u.patronymic,
                'department': u.department.name if u.department else None,
            })

        # Подразделения
        departments = []
        for d in Department.objects.filter(is_active=True):
            departments.append({
                'id': d.pk,
                'name': d.name,
            })

        # Группы рассылки
        groups = []
        for g in ScenarioMailGroup.objects.all():
            groups.append({
                'id': g.pk,
                'name': g.name,
                'member_count': g.member_count,
            })

        # Роли
        roles = []
        for r in Role.objects.filter(is_active=True).order_by('name'):
            roles.append({
                'id': r.pk,
                'name': r.name,
            })

        return {
            'users': users,
            'departments': departments,
            'groups': groups,
            'roles': roles,
        }


class StepUpdateView(LoginRequiredMixin, UpdateView):
    model = Step
    form_class = StepForm
    template_name = 'scenarios/step_form.html'

    def get_success_url(self):
        return reverse('scenarios:scenario_editor', kwargs={'pk': self.object.branch.scenario_id})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Шаг обновлён.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mailing_list_data'] = self._get_mailing_list_data()
        return context

    def _get_mailing_list_data(self):
        """Собирает все данные для виджета списка рассылки."""
        from accounts.models import Department
        from scenarios.models import ScenarioMailGroup

        users = []
        for u in User.objects.filter(archive_status=User.STATUS_ACTIVE).select_related('department'):
            users.append({
                'id': u.pk,
                'tab_number': u.tab_number,
                'last_name': u.last_name,
                'first_name': u.first_name,
                'patronymic': u.patronymic,
                'department': u.department.name if u.department else None,
            })

        departments = []
        for d in Department.objects.filter(is_active=True):
            departments.append({
                'id': d.pk,
                'name': d.name,
            })

        groups = []
        for g in ScenarioMailGroup.objects.all():
            groups.append({
                'id': g.pk,
                'name': g.name,
                'member_count': g.member_count,
            })

        return {
            'users': users,
            'departments': departments,
            'groups': groups,
        }


class StepDeleteView(LoginRequiredMixin, DeleteView):
    model = Step
    template_name = 'scenarios/step_confirm_delete.html'

    def get_success_url(self):
        return reverse('scenarios:scenario_editor', kwargs={'pk': self.object.branch.scenario_id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_success_url()
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Шаг удалён.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# API для выбора result_code
# ============================================================================

def available_result_codes(request):
    """API endpoint: возвращает все result_code для ветки, исключая уже занятые."""
    branch_id = request.GET.get('branch')
    current_code = request.GET.get('current_code', '')

    if not branch_id:
        return JsonResponse({'error': 'branch required'}, status=400)

    # Все шаги ветки
    steps = Step.objects.filter(branch_id=branch_id).order_by('step_order')

    # Уже занятые коды (prev_result_code любых шагов)
    occupied_codes = set(
        Step.objects.exclude(prev_result_code='').values_list('prev_result_code', flat=True)
    )

    # Собираем варианты ответов
    options = []
    for step in steps:
        message_json = step.message_json
        if not isinstance(message_json, dict):
            continue

        msg_type = message_json.get('type', '')

        if msg_type in ('buttons', 'buttons_with_number'):
            for opt in message_json.get('options', []):
                rc = opt.get('result_code', '')
                if rc and rc not in occupied_codes:
                    options.append({
                        'step_order': step.step_order,
                        'prev_result_code': step.prev_result_code or '(первый шаг)',
                        'message_text': step.message_text[:100],
                        'button_text': opt.get('text', ''),
                        'result_code': rc,
                        'ask_number': opt.get('ask_number', False),
                    })

    return JsonResponse({'options': options})


# ============================================================================
# API для виджета списка рассылки
# ============================================================================

def mailing_list_roles(request):
    """API: возвращает список ролей с scope для виджета mailing list."""
    roles = []
    for role in Role.objects.filter(is_active=True).order_by('name'):
        # Собираем уникальные scope для роли
        scopes = set()
        for er in EmployeeRole.objects.filter(role=role).select_related('scope_department'):
            if er.scope_department:
                scopes.add(er.scope_department.name)
        
        scope_label = ', '.join(sorted(scopes)) if scopes else ''
        roles.append({
            'name': role.name,
            'scope_label': scope_label,
        })

    return JsonResponse({'roles': roles})


def mailing_list_mail_groups(request):
    """API: возвращает список групп рассылки для виджета mailing list."""
    groups = []
    for g in ScenarioMailGroup.objects.all().order_by('name'):
        groups.append({
            'id': g.pk,
            'name': g.name,
            'description': g.description,
            'member_count': g.member_count,
        })

    return JsonResponse({'groups': groups})


# ============================================================================
# Запуски
# ============================================================================

class RunListView(LoginRequiredMixin, ListView):
    model = Run
    template_name = 'scenarios/run_list.html'
    context_object_name = 'runs'
    paginate_by = 20

    def get_queryset(self):
        return Run.objects.select_related('scenario', 'started_by').prefetch_related(
            'scenario__branches'
        ).order_by('-started_at')


class RunDetailView(LoginRequiredMixin, DetailView):
    model = Run
    template_name = 'scenarios/run_detail.html'
    context_object_name = 'run'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['step_runs'] = self.object.step_runs.select_related(
            'step', 'step__branch', 'recipient'
        ).prefetch_related('answers').order_by('step__step_order')
        context['answers'] = self.object.answers.select_related('employee').order_by('-received_at')
        context['db_values'] = self.object.db_values.all()
        context['logs'] = self.object.logs.select_related('run').order_by('-created_at')
        return context


class RunStartView(LoginRequiredMixin, FormMixin, DetailView):
    """Запуск сценария."""
    model = Scenario
    template_name = 'scenarios/run_start.html'
    form_class = RunStartForm
    context_object_name = 'scenario'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        context['now'] = timezone.now()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        run = Run.objects.create(
            scenario=self.object,
            started_by=self.request.user,
            params_json=form.cleaned_data,
            status=Run.STATUS_PENDING,
        )

        # Запускаем исполнитель
        executor = ScenarioExecutor(run)
        executor.start()

        messages.success(self.request, f'Сценарий "{self.object}" запущен.')
        return redirect('scenarios:run_detail', pk=run.pk)

    def form_invalid(self, form):
        messages.error(self.request, 'Ошибка в параметрах запуска.')
        return self.render_to_response(self.get_context_data(form=form))


class RunCancelView(LoginRequiredMixin, DetailView):
    model = Run

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = Run.STATUS_CANCELLED
        self.object.save()
        messages.success(request, 'Запуск отменён.')
        return redirect('scenarios:run_detail', pk=self.object.pk)


# ============================================================================
# Журнал
# ============================================================================

class JournalListView(LoginRequiredMixin, ListView):
    model = Log
    template_name = 'scenarios/journal_list.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        qs = Log.objects.select_related('run').prefetch_related(
            'run__scenario'
        ).order_by('-created_at')

        run_id = self.request.GET.get('run')
        if run_id:
            qs = qs.filter(run_id=run_id)

        event_type = self.request.GET.get('event')
        if event_type:
            qs = qs.filter(event_type=event_type)

        return qs


# ============================================================================
# Роли
# ============================================================================

class RoleListView(LoginRequiredMixin, ListView):
    model = Role
    template_name = 'scenarios/role_list.html'
    context_object_name = 'roles'

    def get_queryset(self):
        return Role.objects.prefetch_related(
            Prefetch(
                'employee_roles',
                queryset=EmployeeRole.objects.select_related(
                    'employee__department',
                    'employee__position',
                    'scope_department',
                ).order_by('employee__last_name', 'employee__first_name'),
            )
        ).order_by('name')


class RoleCreateView(LoginRequiredMixin, CreateView):
    model = Role
    fields = ['name']
    template_name = 'scenarios/role_form.html'
    success_url = reverse_lazy('scenarios:role_list')


class RoleUpdateView(LoginRequiredMixin, UpdateView):
    model = Role
    fields = ['name']
    template_name = 'scenarios/role_form.html'
    success_url = reverse_lazy('scenarios:role_list')


class RoleDetailView(LoginRequiredMixin, DetailView):
    """Детали роли — список привязанных сотрудников."""
    model = Role
    template_name = 'scenarios/role_detail.html'
    context_object_name = 'role'

    def get_queryset(self):
        return Role.objects.prefetch_related(
            'employee_roles__employee__department',
            'employee_roles__employee__position',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employee_roles'] = self.object.employee_roles.select_related(
            'employee', 'employee__department', 'employee__position', 'scope_department'
        ).order_by('employee__last_name', 'employee__first_name')
        context['all_users'] = list(
            User.objects.filter(archive_status=User.STATUS_ACTIVE).values(
                'pk', 'last_name', 'first_name', 'patronymic',
                'department__name', 'position__name'
            ).order_by('last_name', 'first_name')
        )
        return context


class RoleAddUserView(LoginRequiredMixin, DetailView):
    """Добавление сотрудника к роли."""
    model = Role

    def dispatch(self, request, *args, **kwargs):
        if request.method != 'POST':
            return redirect('scenarios:role_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        role = self.get_object()
        user_id = request.POST.get('user_id')
        dept_id = request.POST.get('dept_id', '')
        if user_id:
            user = get_object_or_404(User, pk=user_id)
            scope = None
            if dept_id:
                scope = get_object_or_404(Department, pk=dept_id)
            EmployeeRole.objects.get_or_create(
                employee=user,
                role=role,
                scope_department=scope,
            )
            messages.success(request, f'{user.get_full_name()} привязан(а) к роли "{role.name}".')
        return redirect('scenarios:role_detail', pk=role.pk)


class RoleRemoveUserView(LoginRequiredMixin, DetailView):
    """Отвязка сотрудника от роли."""
    model = Role

    def dispatch(self, request, *args, **kwargs):
        if request.method != 'POST':
            return redirect('scenarios:role_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        role = self.get_object()
        user_id = request.POST.get('user_id')
        if user_id:
            er = get_object_or_404(EmployeeRole, employee_id=user_id, role=role)
            user = er.employee
            er.delete()
            messages.success(request, f'{user.get_full_name()} отвязан(а) от роли "{role.name}".')
        return redirect('scenarios:role_detail', pk=role.pk)


class RoleDeleteView(LoginRequiredMixin, DeleteView):
    model = Role
    success_url = reverse_lazy('scenarios:role_list')


# ============================================================================
# Обработка ответов от бота (JSON API)
# ============================================================================

def process_bot_answer(request):
    """
    API endpoint для обработки ответов от MAX-бота.
    Вызывается ботом при получении ответа от пользователя.

    POST /scenarios/api/answer/
    {
        "user_id": 15284524,
        "message_text": "Палата 5 — 12",
        "button_result_code": "EVAC_YES"  // опционально
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    user_id = data.get('user_id')
    message_text = data.get('message_text', '')
    button_result_code = data.get('button_result_code')

    if not user_id:
        return JsonResponse({'error': 'user_id required'}, status=400)

    # Находим активный run для пользователя
    from django.utils import timezone
    active_step_run = StepRun.objects.filter(
        recipient_id=user_id,
        status=StepRun.STATUS_SENT,
        run__status=Run.STATUS_RUNNING,
    ).order_by('step__step_order').first()

    if not active_step_run:
        return JsonResponse({
            'success': False,
            'error': 'Нет активного шага',
        })

    run = active_step_run.run
    executor = ScenarioExecutor(run)

    result = executor.process_answer(user_id, message_text, button_result_code)

    return JsonResponse(result)


# ============================================================================
# Группы рассылки сценариев
# ============================================================================

class ScenarioMailGroupListView(LoginRequiredMixin, ListView):
    """Список групп рассылки сценариев."""
    model = ScenarioMailGroup
    template_name = 'scenarios/mail_group_list.html'
    context_object_name = 'groups'

    def get_queryset(self):
        return ScenarioMailGroup.objects.select_related('created_by').prefetch_related(
            'users', 'departments'
        ).order_by('name')


class ScenarioMailGroupCreateView(LoginRequiredMixin, CreateView):
    """Создание группы рассылки сценариев."""
    model = ScenarioMailGroup
    form_class = ScenarioMailGroupForm
    template_name = 'scenarios/mail_group_form.html'

    def get_success_url(self):
        return reverse_lazy('scenarios:mail_group_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._get_mailing_options())
        context['direct_users'] = []
        context['direct_depts'] = []
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        self._set_m2m_fields(form.instance)
        return response

    def _set_m2m_fields(self, instance):
        """Установка M2M полей из скрытых полей формы."""
        recipients_ids = self.request.POST.get('recipients', '').strip().split(',')
        departments_ids = self.request.POST.get('departments', '').strip().split(',')

        recipients_ids = [rid for rid in recipients_ids if rid]
        departments_ids = [did for did in departments_ids if did]

        if recipients_ids:
            instance.users.set(recipients_ids)
        if departments_ids:
            instance.departments.set(departments_ids)

    def _get_mailing_options(self):
        """Собирает данные для виджетов выбора сотрудников и подразделений."""
        users = []
        for u in User.objects.filter(archive_status=User.STATUS_ACTIVE).select_related('department'):
            users.append({
                'id': u.pk,
                'last_name': u.last_name,
                'first_name': u.first_name,
                'patronymic': u.patronymic,
                'department': u.department.name if u.department else None,
            })

        departments = []
        for d in Department.objects.filter(is_active=True):
            departments.append({
                'id': d.pk,
                'name': d.name,
            })

        return {'users': users, 'depts': departments}


class ScenarioMailGroupUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование группы рассылки сценариев."""
    model = ScenarioMailGroup
    form_class = ScenarioMailGroupForm
    template_name = 'scenarios/mail_group_form.html'

    def get_success_url(self):
        return reverse_lazy('scenarios:mail_group_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._get_mailing_options())
        context['direct_users'] = self.object.users.select_related('department', 'position').order_by('last_name', 'first_name')
        context['direct_depts'] = self.object.departments.all()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        self._set_m2m_fields(form.instance)
        return response

    def _set_m2m_fields(self, instance):
        """Установка M2M полей из скрытых полей формы."""
        recipients_ids = self.request.POST.get('recipients', '').strip().split(',')
        departments_ids = self.request.POST.get('departments', '').strip().split(',')

        recipients_ids = [rid for rid in recipients_ids if rid]
        departments_ids = [did for did in departments_ids if did]

        if recipients_ids:
            instance.users.set(recipients_ids)
        if departments_ids:
            instance.departments.set(departments_ids)

    def _get_mailing_options(self):
        """Собирает данные для виджетов выбора сотрудников и подразделений."""
        users = []
        for u in User.objects.filter(archive_status=User.STATUS_ACTIVE).select_related('department'):
            users.append({
                'id': u.pk,
                'last_name': u.last_name,
                'first_name': u.first_name,
                'patronymic': u.patronymic,
                'department': u.department.name if u.department else None,
            })

        departments = []
        for d in Department.objects.filter(is_active=True):
            departments.append({
                'id': d.pk,
                'name': d.name,
            })

        return {'users': users, 'depts': departments}


class ScenarioMailGroupDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о группе рассылки сценариев."""
    model = ScenarioMailGroup
    template_name = 'scenarios/mail_group_detail.html'
    context_object_name = 'group'

    def get_queryset(self):
        return ScenarioMailGroup.objects.prefetch_related('users', 'departments')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from accounts.models import User
        group = self.get_object()
        context['all_users'] = User.objects.filter(
            pk__in=group.user_ids
        ).select_related('department', 'position').order_by('last_name', 'first_name')
        context['direct_users'] = group.users.select_related('department', 'position').order_by('last_name', 'first_name')
        context['direct_users_ids'] = set(group.users.values_list('pk', flat=True))
        context['direct_depts'] = group.departments.all()

        # Данные для поиска добавления
        context['users'] = list(
            User.objects.filter(archive_status=User.STATUS_ACTIVE).values('pk', 'last_name', 'first_name', 'department__name')
        )
        context['depts'] = list(
            Department.objects.filter(is_active=True).values('pk', 'name')
        )
        return context


class ScenarioMailGroupDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление группы рассылки сценариев."""
    model = ScenarioMailGroup
    template_name = 'scenarios/mail_group_confirm_delete.html'
    success_url = reverse_lazy('scenarios:mail_group_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Группа рассылки удалена.')
        return super().delete(request, *args, **kwargs)


class ScenarioMailGroupAddUserView(LoginRequiredMixin, DetailView):
    """Добавление пользователя в группу."""
    model = ScenarioMailGroup

    def dispatch(self, request, *args, **kwargs):
        if request.method != 'POST':
            return redirect('scenarios:mail_group_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        group = self.get_object()
        user_id = request.POST.get('user_id')
        if user_id:
            user = get_object_or_404(User, pk=user_id)
            group.users.add(user)
            messages.success(request, f'{user.get_full_name()} добавлен(а) в группу "{group.name}".')
        return redirect('scenarios:mail_group_detail', pk=group.pk)


class ScenarioMailGroupRemoveUserView(LoginRequiredMixin, DetailView):
    """Удаление пользователя из группы."""
    model = ScenarioMailGroup

    def dispatch(self, request, *args, **kwargs):
        if request.method != 'POST':
            return redirect('scenarios:mail_group_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        group = self.get_object()
        user_id = request.POST.get('user_id')
        if user_id:
            user = get_object_or_404(User, pk=user_id)
            group.users.remove(user)
            messages.success(request, f'{user.get_full_name()} удалён(а) из группы "{group.name}".')
        return redirect('scenarios:mail_group_detail', pk=group.pk)


class ScenarioMailGroupAddDeptView(LoginRequiredMixin, DetailView):
    """Добавление подразделения в группу."""
    model = ScenarioMailGroup

    def dispatch(self, request, *args, **kwargs):
        if request.method != 'POST':
            return redirect('scenarios:mail_group_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        group = self.get_object()
        dept_id = request.POST.get('dept_id')
        if dept_id:
            dept = get_object_or_404(Department, pk=dept_id)
            group.departments.add(dept)
            messages.success(request, f'Подразделение "{dept.name}" добавлено в группу "{group.name}".')
        return redirect('scenarios:mail_group_detail', pk=group.pk)


class ScenarioMailGroupRemoveDeptView(LoginRequiredMixin, DetailView):
    """Удаление подразделения из группы."""
    model = ScenarioMailGroup

    def dispatch(self, request, *args, **kwargs):
        if request.method != 'POST':
            return redirect('scenarios:mail_group_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        group = self.get_object()
        dept_id = request.POST.get('dept_id')
        if dept_id:
            dept = get_object_or_404(Department, pk=dept_id)
            group.departments.remove(dept)
            messages.success(request, f'Подразделение "{dept.name}" удалено из группы "{group.name}".')
        return redirect('scenarios:mail_group_detail', pk=group.pk)
