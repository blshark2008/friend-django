from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.views.generic.edit import FormMixin
from django.db.models import Q, Count, Max, Prefetch
from django.http import JsonResponse
from django.utils import timezone
import json
import logging

from .models import (
    Category, Scenario, Branch, Step,
    Run, StepRun, Answer, DbValue, Log,
    Role, EmployeeRole,
    ScenarioMailGroup,
    AnswerSummaryConfig,
)
from .forms import (
    CategoryForm, ScenarioForm, BranchForm, StepForm,
    RunStartForm, ScenarioEditorForm,
    ScenarioMailGroupForm,
)
from .services.executor import ScenarioExecutor
from accounts.models import User, Department

logger = logging.getLogger(__name__)


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
        branches = self.object.branches.all().prefetch_related('steps')
        # Сортируем шаги: сначала без result_code (корневые), затем группируем
        # по message_json.result_code (код результата действия), внутри — по step_order
        def get_result_code(step):
            rc = step.message_json.get('result_code', '')
            return rc if rc else ''

        context['branches'] = []
        for branch in branches:
            steps = list(branch.steps.all().order_by('step_order'))
            root_steps = [s for s in steps if not get_result_code(s)]
            child_steps = [s for s in steps if get_result_code(s)]
            child_steps.sort(key=lambda s: (get_result_code(s), s.step_order))
            sorted_steps = root_steps + child_steps
            context['branches'].append({
                'pk': branch.pk,
                'name': branch.name,
                'code': branch.code,
                'steps': sorted_steps,
            })
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
    """API endpoint: возвращает все result_code для ветки, показывая все варианты."""
    branch_id = request.GET.get('branch')
    current_code = request.GET.get('current_code', '')

    if not branch_id:
        return JsonResponse({'error': 'branch required'}, status=400)

    # Все шаги ветки
    steps = Step.objects.filter(branch_id=branch_id).order_by('step_order')

    # Уже занятые коды (prev_result_code любых шагов) — для визуального выделения
    occupied_codes = set(
        Step.objects.exclude(prev_result_code='').values_list('prev_result_code', flat=True)
    )

    # Собираем варианты ответов из ВСЕХ типов шагов
    options = []
    for step in steps:
        message_json = step.message_json
        if not isinstance(message_json, dict):
            continue

        msg_type = message_json.get('type', '')

        # Кнопки
        if msg_type in ('buttons', 'buttons_with_number'):
            for opt in message_json.get('options', []):
                rc = opt.get('result_code', '')
                if rc:
                    options.append({
                        'step_order': step.step_order,
                        'prev_result_code': step.prev_result_code or '(первый шаг)',
                        'message_text': step.message_text[:100],
                        'button_text': opt.get('text', ''),
                        'result_code': rc,
                        'ask_number': opt.get('ask_number', False),
                        'variant_type': 'Кнопка',
                        'is_occupied': rc in occupied_codes,
                    })

        # Число
        elif msg_type == 'number':
            rc = message_json.get('result_code', '')
            if rc:
                options.append({
                    'step_order': step.step_order,
                    'prev_result_code': step.prev_result_code or '(первый шаг)',
                    'message_text': step.message_text[:100],
                    'button_text': 'Число',
                    'result_code': rc,
                    'ask_number': False,
                    'variant_type': 'Число',
                    'is_occupied': rc in occupied_codes,
                })

        # Текст
        elif msg_type == 'text_pattern':
            rc = message_json.get('result_code', '')
            if rc:
                options.append({
                    'step_order': step.step_order,
                    'prev_result_code': step.prev_result_code or '(первый шаг)',
                    'message_text': step.message_text[:100],
                    'button_text': 'Текст',
                    'result_code': rc,
                    'ask_number': False,
                    'variant_type': 'Текст',
                    'is_occupied': rc in occupied_codes,
                })

        # Выбор изображения
        elif msg_type == 'image_selection':
            rc = message_json.get('result_code', '')
            if rc:
                options.append({
                    'step_order': step.step_order,
                    'prev_result_code': step.prev_result_code or '(первый шаг)',
                    'message_text': step.message_text[:100],
                    'button_text': 'Изображение',
                    'result_code': rc,
                    'ask_number': False,
                    'variant_type': 'Изображение',
                    'is_occupied': rc in occupied_codes,
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


@login_required
def run_bulk_delete(request):
    """Групповое удаление запусков."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    run_ids = request.POST.getlist('run_ids')
    if not run_ids:
        messages.warning(request, 'Не выбрано ни одного запуска')
        return redirect('scenarios:run_list')

    # Запрещаем удаление активных запусков
    active_runs = Run.objects.filter(pk__in=run_ids, status=Run.STATUS_RUNNING)
    if active_runs.exists():
        messages.error(request, f'Нельзя удалить {active_runs.count()} выполняющийся(их) запуск(ов)')
        return redirect('scenarios:run_list')

    count = Run.objects.filter(pk__in=run_ids).delete()
    messages.success(request, f'Удалено {count[0]} запуск(ов)')
    return redirect('scenarios:run_list')


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
        context['summary_data'] = self._compute_summary_data()
        return context

    def _compute_summary_data(self):
        """Вычисляет сводные данные на основе AnswerSummaryConfig и ответов."""
        configs = AnswerSummaryConfig.objects.filter(scenario=self.object.scenario)
        if not configs.exists():
            return []

        result = []
        for config in configs:
            # Находим все StepRun с этим result_code для данного run
            step_runs = self.object.step_runs.filter(result_code=config.result_code)
            step_run_ids = step_runs.values_list('pk', flat=True)
            answers = self.object.answers.filter(step_run__in=step_run_ids).select_related('employee', 'employee__department')

            # Определяем отображаемый текст по result_code
            display_label = self._get_result_code_label(config.result_code)

            # Собираем числовые значения и группировку текстовых ответов
            numeric_values = []
            value_counts = {}
            dept_data = {}  # Группировка по подразделениям

            for answer in answers:
                answer_json = answer.answer_json
                employee = answer.employee
                dept = employee.department

                # Определяем текстовое значение для группировки
                if isinstance(answer_json, dict):
                    num_val = answer_json.get('value') or answer_json.get('number') or answer_json.get('answer')
                    if num_val is not None:
                        try:
                            numeric_values.append(float(num_val))
                        except (ValueError, TypeError):
                            pass
                    text_val = answer_json.get('text') or answer_json.get('answer') or str(answer_json)
                elif isinstance(answer_json, (int, float)):
                    numeric_values.append(float(answer_json))
                    text_val = str(answer_json)
                else:
                    text_val = str(answer_json) if answer_json else ''

                # Группировка по значению
                if text_val:
                    value_counts[text_val] = value_counts.get(text_val, 0) + 1

                # Группировка по подразделениям
                dept_name = dept.name if dept else 'Не определено'
                if dept_name not in dept_data:
                    dept_data[dept_name] = {
                        'dept': dept,
                        'employees': {},  # {emp_id: {'name': ..., 'answers': [], 'sum': 0}}
                        'total_sum': 0,
                        'total_count': 0,
                        'value_counts': {},
                    }

                emp = dept_data[dept_name]['employees']
                if employee.pk not in emp:
                    emp[employee.pk] = {
                        'name': employee.get_full_name(),
                        'answers': [],
                        'sum': 0,
                    }

                emp[employee.pk]['answers'].append(text_val)

                # Числовое значение для подразделения и сотрудника
                if num_val is not None:
                    try:
                        num_float = float(num_val)
                        emp[employee.pk]['sum'] += num_float
                        dept_data[dept_name]['total_sum'] += num_float
                    except (ValueError, TypeError):
                        pass

                dept_data[dept_name]['total_count'] += 1

                if text_val:
                    dept_data[dept_name]['value_counts'][text_val] = dept_data[dept_name]['value_counts'].get(text_val, 0) + 1

            total_sum = sum(numeric_values) if numeric_values else 0
            total_count = answers.count()

            # Преобразуем dept_data в список для шаблона
            dept_list = []
            for dept_name, data in dept_data.items():
                emp_list = []
                for emp_id, emp_info in data['employees'].items():
                    # Группировка ответов сотрудника
                    emp_value_counts = {}
                    emp_total_sum = 0
                    for a in emp_info['answers']:
                        emp_value_counts[a] = emp_value_counts.get(a, 0) + 1
                    # Сумма по сотруднику
                    if 'total_sum' in emp_info:
                        emp_total_sum = emp_info['total_sum']
                    
                    emp_list.append({
                        'name': emp_info['name'],
                        'answer_count': len(emp_info['answers']),
                        'value_counts': emp_value_counts,
                        'total_sum': emp_total_sum,
                    })

                dept_list.append({
                    'name': dept_name,
                    'total_sum': data['total_sum'],
                    'total_count': data['total_count'],
                    'value_counts': data['value_counts'],
                    'employees': emp_list,
                })

            result.append({
                'config': config,
                'display_label': display_label,
                'total_sum': total_sum,
                'total_count': total_count,
                'value_counts': value_counts,
                'has_numeric': config.aggregate_numeric and len(numeric_values) > 0,
                'dept_data': dept_list,
            })

        return result

    def _get_result_code_label(self, result_code):
        """Определяет отображаемый текст по result_code из шага сценария."""
        if not result_code:
            return '—'
        
        # Ищем все шаги сценария
        steps = Step.objects.filter(
            branch__scenario=self.object.scenario,
        ).select_related('branch').distinct()
        
        for step in steps:
            message_json = step.message_json
            if not isinstance(message_json, dict):
                continue
            
            msg_type = message_json.get('type', '')
            
            # Кнопки - ищем result_code в options
            if msg_type in ('buttons', 'buttons_with_number'):
                options = message_json.get('options', [])
                for opt in options:
                    if opt.get('result_code') == result_code:
                        return opt.get('text', result_code)
            
            # Число
            elif msg_type == 'number':
                # Проверяем, что result_code совпадает с result_code в message_json
                if message_json.get('result_code') == result_code:
                    return 'Число'
            
            # Текст
            elif msg_type == 'text_pattern':
                if message_json.get('result_code') == result_code:
                    return 'Текст'
            
            # Изображение
            elif msg_type == 'image_selection':
                if message_json.get('result_code') == result_code:
                    return 'Изображение'
        
        return result_code


def run_summary_api(request, pk):
    """API endpoint для получения данных сводной таблицы в JSON формате."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    run = get_object_or_404(Run, pk=pk)

    configs = AnswerSummaryConfig.objects.filter(scenario=run.scenario)
    if not configs.exists():
        return JsonResponse({'summary_data': [], 'has_configs': False})

    result = []
    for config in configs:
        # Определяем отображаемый текст по result_code
        display_label = _get_result_code_label_for_scenario(run.scenario, config.result_code)

        step_runs = run.step_runs.filter(result_code=config.result_code)
        step_run_ids = step_runs.values_list('pk', flat=True)
        answers = run.answers.filter(step_run__in=step_run_ids).select_related('employee', 'employee__department')

        numeric_values = []
        value_counts = {}
        dept_data = {}

        for answer in answers:
            answer_json = answer.answer_json
            employee = answer.employee
            dept = employee.department

            if isinstance(answer_json, dict):
                num_val = answer_json.get('value') or answer_json.get('number') or answer_json.get('answer')
                if num_val is not None:
                    try:
                        numeric_values.append(float(num_val))
                    except (ValueError, TypeError):
                        pass
                text_val = answer_json.get('text') or answer_json.get('answer') or str(answer_json)
            elif isinstance(answer_json, (int, float)):
                numeric_values.append(float(answer_json))
                text_val = str(answer_json)
            else:
                text_val = str(answer_json) if answer_json else ''

            if text_val:
                value_counts[text_val] = value_counts.get(text_val, 0) + 1

            dept_name = dept.name if dept else 'Не определено'
            if dept_name not in dept_data:
                dept_data[dept_name] = {
                    'employees': {},
                    'total_sum': 0,
                    'total_count': 0,
                    'value_counts': {},
                }

            emp = dept_data[dept_name]['employees']
            if employee.pk not in emp:
                emp[employee.pk] = {
                    'name': employee.get_full_name(),
                    'answers': [],
                    'sum': 0,
                }

            emp[employee.pk]['answers'].append(text_val)

            if num_val is not None:
                try:
                    num_float = float(num_val)
                    emp[employee.pk]['sum'] += num_float
                    dept_data[dept_name]['total_sum'] += num_float
                except (ValueError, TypeError):
                    pass

            dept_data[dept_name]['total_count'] += 1

            if text_val:
                dept_data[dept_name]['value_counts'][text_val] = dept_data[dept_name]['value_counts'].get(text_val, 0) + 1

        total_sum = sum(numeric_values) if numeric_values else 0
        total_count = answers.count()

        dept_list = []
        for dept_name, data in dept_data.items():
            emp_list = []
            for emp_id, emp_info in data['employees'].items():
                emp_value_counts = {}
                for a in emp_info['answers']:
                    emp_value_counts[a] = emp_value_counts.get(a, 0) + 1
                emp_list.append({
                    'name': emp_info['name'],
                    'answer_count': len(emp_info['answers']),
                    'value_counts': emp_value_counts,
                    'total_sum': emp_info.get('sum', 0),
                })

            dept_list.append({
                'name': dept_name,
                'total_sum': data['total_sum'],
                'total_count': data['total_count'],
                'value_counts': data['value_counts'],
                'employees': emp_list,
            })

        result.append({
            'config': {
                'id': config.pk,
                'result_code': config.result_code,
                'display_text': config.display_text,
                'aggregate_numeric': config.aggregate_numeric,
            },
            'display_label': display_label,
            'total_sum': total_sum,
            'total_count': total_count,
            'value_counts': value_counts,
            'has_numeric': config.aggregate_numeric and len(numeric_values) > 0,
            'dept_data': dept_list,
        })

    return JsonResponse({
        'summary_data': result,
        'has_configs': True,
        'run_status': run.status,
        'updated_at': timezone.now().isoformat(),
    })


def _get_result_code_label_for_scenario(scenario, result_code):
    """Определяет отображаемый текст по result_code из шагов сценария."""
    if not result_code:
        return '—'
    
    # Ищем все шаги сценария
    steps = Step.objects.filter(
        branch__scenario=scenario,
    ).select_related('branch').distinct()
    
    for step in steps:
        message_json = step.message_json
        if not isinstance(message_json, dict):
            continue
        
        msg_type = message_json.get('type', '')
        
        # Кнопки - ищем result_code в options
        if msg_type in ('buttons', 'buttons_with_number'):
            options = message_json.get('options', [])
            for opt in options:
                if opt.get('result_code') == result_code:
                    return opt.get('text', result_code)
        
        # Число
        elif msg_type == 'number':
            if message_json.get('result_code') == result_code:
                return 'Число'
        
        # Текст
        elif msg_type == 'text_pattern':
            if message_json.get('result_code') == result_code:
                return 'Текст'
        
        # Изображение
        elif msg_type == 'image_selection':
            if message_json.get('result_code') == result_code:
                return 'Изображение'
    
    return result_code


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
        
        # Очищаем UserCurrentRun для всех пользователей этого запуска
        from scenarios.models import UserCurrentRun
        UserCurrentRun.objects.filter(run=self.object).delete()
        
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


# ============================================================================
# Настройка обработки ответов
# ============================================================================

class AnswerConfigView(LoginRequiredMixin, DetailView):
    """Страница настройки обработки ответов сценария."""
    model = Scenario
    template_name = 'scenarios/answer_config.html'
    context_object_name = 'scenario'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['branches'] = self.object.branches.all().prefetch_related('steps')
        context['configs'] = AnswerSummaryConfig.objects.filter(
            scenario=self.object
        ).order_by('result_code')
        return context


def answer_config_add(request):
    """AJAX: добавить конфигурацию сводки."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    scenario_id = data.get('scenario_id')
    result_code = data.get('result_code', '')
    display_text = data.get('display_text', '')

    if not scenario_id or not result_code or not display_text:
        return JsonResponse({'error': 'Missing fields'}, status=400)

    scenario = get_object_or_404(Scenario, pk=scenario_id)

    config, created = AnswerSummaryConfig.objects.update_or_create(
        scenario=scenario,
        result_code=result_code,
        defaults={
            'display_text': display_text,
            'aggregate_numeric': True,
        },
    )

    return JsonResponse({
        'success': True,
        'id': config.pk,
        'created': created,
        'message': 'Добавлено' if created else 'Обновлено',
    })


def answer_config_delete(request):
    """AJAX: удалить конфигурацию сводки."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    config_id = data.get('config_id')
    if not config_id:
        return JsonResponse({'error': 'config_id required'}, status=400)

    config = get_object_or_404(AnswerSummaryConfig, pk=config_id)
    scenario_id = config.scenario_id
    config.delete()

    return JsonResponse({'success': True, 'message': 'Удалено'})


def answer_config_update(request):
    """AJAX: обновить конфигурацию сводки."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    config_id = data.get('config_id')
    display_text = data.get('display_text', '').strip()
    result_code = data.get('result_code', '').strip()
    aggregate_numeric = data.get('aggregate_numeric', True)

    if not config_id:
        return JsonResponse({'error': 'config_id required'}, status=400)
    if not display_text:
        return JsonResponse({'error': 'display_text required'}, status=400)

    config = get_object_or_404(AnswerSummaryConfig, pk=config_id)
    original_result_code = config.result_code
    
    # Проверяем, не занят ли новый result_code другим конфигом
    if result_code and result_code != original_result_code:
        exists = AnswerSummaryConfig.objects.filter(
            scenario=config.scenario,
            result_code=result_code,
        ).exclude(pk=config_id).exists()
        if exists:
            return JsonResponse({'error': f'Код результата "{result_code}" уже используется'}, status=400)
    
    config.display_text = display_text
    config.result_code = result_code
    config.aggregate_numeric = aggregate_numeric
    config.save()

    return JsonResponse({
        'success': True,
        'message': 'Обновлено',
    })


# ============================================================================
# Сохранение сообщений сценария
# ============================================================================

def save_scenario_messages(request):
    """AJAX: сохранить сообщения отбоя и отмены."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    scenario_id = data.get('scenario_id')
    abort_message = data.get('abort_message', '')
    cancel_message = data.get('cancel_message', '')

    if not scenario_id:
        return JsonResponse({'error': 'scenario_id required'}, status=400)

    scenario = get_object_or_404(Scenario, pk=scenario_id)
    scenario.abort_message = abort_message
    scenario.cancel_message = cancel_message
    scenario.save(update_fields=['abort_message', 'cancel_message'])

    return JsonResponse({'success': True, 'message': 'Сохранено'})


# ============================================================================
# Отбой тревоги / Отмена сценария
# ============================================================================

def run_abort_view(request, pk):
    """Завершение сценария с отправкой сообщения отбоя."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    run = get_object_or_404(Run, pk=pk)
    
    if run.status != Run.STATUS_RUNNING:
        return JsonResponse({'error': 'Сценарий не выполняется'}, status=400)

    scenario = run.scenario
    message = scenario.abort_message

    if not message:
        return JsonResponse({'error': 'Сообщение отбоя не настроено'}, status=400)

    try:
        _send_abort_cancel_message(run, message, 'abort')
        run.status = Run.STATUS_COMPLETED
        run.completed_at = timezone.now()
        run.save(update_fields=['status', 'completed_at'])

        # Очищаем UserCurrentRun для всех пользователей этого запуска
        from scenarios.models import UserCurrentRun
        UserCurrentRun.objects.filter(run=run).delete()

        Log.objects.create(
            run=run,
            event_type=Log.EVENT_RUN_COMPLETED,
            payload_json={
                'aborted': True,
                'message': message,
            },
        )

        return JsonResponse({
            'success': True,
            'message': 'Сценарий завершён (отбой)',
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def run_cancel_action_view(request, pk):
    """Отмена сценария с отправкой сообщения отмены."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    run = get_object_or_404(Run, pk=pk)
    
    if run.status != Run.STATUS_RUNNING:
        return JsonResponse({'error': 'Сценарий не выполняется'}, status=400)

    scenario = run.scenario
    message = scenario.cancel_message

    if not message:
        return JsonResponse({'error': 'Сообщение отмены не настроено'}, status=400)

    try:
        _send_abort_cancel_message(run, message, 'cancel')
        run.status = Run.STATUS_CANCELLED
        run.completed_at = timezone.now()
        run.save(update_fields=['status', 'completed_at'])

        # Очищаем UserCurrentRun для всех пользователей этого запуска
        from scenarios.models import UserCurrentRun
        UserCurrentRun.objects.filter(run=run).delete()

        Log.objects.create(
            run=run,
            event_type=Log.EVENT_RUN_COMPLETED,
            payload_json={
                'cancelled': True,
                'message': message,
            },
        )

        return JsonResponse({
            'success': True,
            'message': 'Сценарий отменён',
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _send_abort_cancel_message(run, message, msg_type):
    """
    Отправляет сообщение отбоя/отмены всем сотрудникам в рамках запуска.
    
    Args:
        run: Запуск сценария
        message: Текст сообщения
        msg_type: 'abort' или 'cancel'
    """
    from messaging.services.bot_api_client import bot_api_client
    
    # Собираем всех получателей из всех веток
    all_recipients = set()
    for branch in run.scenario.branches.all():
        recipients = _resolve_branch_recipients(branch, run)
        all_recipients.update(recipients)

    # Отправляем сообщение каждому
    sent_count = 0
    failed_count = 0
    
    for recipient in all_recipients:
        try:
            user = User.objects.filter(pk=recipient.pk).first()
            if not user or not user.max_id:
                logger.warning(f'У пользователя {recipient.pk} нет max_id — пропущен')
                failed_count += 1
                continue

            bot_api_client.send_message(
                user_id=int(user.max_id),
                text=message,
                format='html',
            )
            sent_count += 1

            # Лог
            Log.objects.create(
                run=run,
                event_type=Log.EVENT_RUN_COMPLETED,
                payload_json={
                    'message_type': msg_type,
                    'user_id': recipient.pk,
                    'user_name': user.get_full_name(),
                    'message': message[:200],
                },
            )
        except Exception as e:
            logger.error(f'Ошибка отправки сообщения пользователю {recipient.pk}: {e}')
            failed_count += 1

    logger.info(f'Отправлено {sent_count}, ошибок {failed_count} (тип: {msg_type})')


def _resolve_branch_recipients(branch, run):
    """Резоллит получателей для ветки."""
    from scenarios.models import EmployeeRole, Role, ScenarioMailGroup
    
    recipients = set()
    
    # Собираем все шаги ветки
    steps = branch.steps.all()
    for step in steps:
        mailing = step.mailing_list_json
        if not isinstance(mailing, list):
            continue

        for item in mailing:
            if not isinstance(item, dict):
                continue

            item_type = item.get('type', '')
            value = item.get('value', '')

            if item_type == 'role':
                role = Role.objects.filter(pk=value).first()
                if role:
                    for er in EmployeeRole.objects.filter(role=role):
                        if er.employee.is_active:
                            recipients.add(er.employee)
            elif item_type == 'user':
                user = User.objects.filter(pk=value).first()
                if user and user.is_active:
                    recipients.add(user)
            elif item_type == 'department':
                dept = Department.objects.filter(pk=value).first()
                if dept:
                    for u in User.objects.filter(department=dept, is_active=True):
                        recipients.add(u)
            elif item_type == 'mail_group':
                group = ScenarioMailGroup.objects.filter(pk=value).first()
                if group:
                    for u in group.users.all():
                        recipients.add(u)
                    for dept in group.departments.all():
                        for u in User.objects.filter(department=dept, is_active=True):
                            recipients.add(u)

    # Фильтруем: только пользователи с max_id
    from accounts.models import User as AccountUser
    recipient_ids = [r.pk for r in recipients]
    users_with_max = AccountUser.objects.filter(
        pk__in=recipient_ids
    ).exclude(max_id__isnull=True).exclude(max_id='')
    
    return list(users_with_max)
