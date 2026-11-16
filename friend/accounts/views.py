from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils import timezone

from rest_framework import viewsets, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import LoginForm, UserEditForm
from .models import Department, Position
from .serializers import DepartmentSerializer, PositionSerializer

from django.views.generic import TemplateView, ListView, DetailView
from django.db import models, transaction
from django.db.models import CharField, Value
from django.db.models.functions import Concat
from django.contrib.auth.mixins import LoginRequiredMixin

import csv
import io
from datetime import datetime

from .models import User, Department

# --- Страницы авторизации через сайт ---

class LoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm

    def get_success_url(self):
        return self.get_redirect_url() or '/accounts/'


class LogoutView(auth_views.LogoutView):
    pass


# --- API для справочников ---

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]


# ============================================================================
# API для пользователей
# ============================================================================

class UserSimpleSerializer(serializers.ModelSerializer):
    """Сериализатор для списка пользователей (минимальные поля)."""
    full_name = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'tab_number', 'last_name', 'first_name', 'patronymic', 'full_name', 'department']

    def get_full_name(self, obj):
        parts = [obj.last_name, obj.first_name]
        if obj.patronymic:
            parts.append(obj.patronymic)
        return ' '.join(parts)

    def get_department(self, obj):
        if obj.department:
            return obj.department.name
        return None


class UserViewSet(viewsets.ModelViewSet):
    """API для получения списка пользователей."""
    queryset = User.objects.filter(
        archive_status=User.STATUS_ACTIVE
    ).select_related('department', 'position')
    serializer_class = UserSimpleSerializer
    permission_classes = [IsAuthenticated]
    paginate_by = 500


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/home.html'
    login_url = 'login'   # если не вошёл — отправит на страницу входа

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments_count'] = Department.objects.filter(is_active=True).count()
        return context


class UserListView(LoginRequiredMixin, ListView):
    """Список пользователей."""
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    SORT_FIELDS = {
        'tab_number': 'tab_number',
        'username': 'username',
        'full_name': 'last_name',
        'department': 'department__name',
        'position': 'position__name',
        'corporate_email': 'corporate_email',
        'corporate_phone': 'corporate_phone',
        'personal_email': 'personal_email',
        'personal_phone': 'personal_phone',
    }

    def get_queryset(self):
        qs = User.objects.select_related('department', 'position').all()
        q = self.request.GET.get('q', '').strip()
        sort = self.request.GET.get('sort', '').strip()
        order = self.request.GET.get('order', 'asc')
        show_archived = self.request.GET.get('show_archived', '0') == '1'
        dept_id = self.request.GET.get('dept_id', '').strip()
        mol_filter = self.request.GET.get('mol', '').strip()

        if not show_archived:
            qs = qs.filter(
                models.Q(archive_status=User.STATUS_ACTIVE) | models.Q(is_admin=True)
            )

        # Фильтр по подразделению
        if dept_id:
            qs = qs.filter(department_id=dept_id)

        # Фильтр по МОЛ
        if mol_filter == 'mol':
            qs = qs.filter(is_mol=True)
        elif mol_filter == 'not_mol':
            qs = qs.filter(is_mol=False)

        if q:
            words = q.split()

            if len(words) >= 2:
                # Если 2+ слова — ищем по полному ФИО как строке
                # Аннотируем полное ФИО
                qs = qs.annotate(
                    full_name=models.Case(
                        models.When(
                            patronymic='',
                            then=Concat('last_name', Value(' '), 'first_name'),
                        ),
                        default=Concat('last_name', Value(' '), 'first_name', Value(' '), 'patronymic'),
                        output_field=models.CharField(),
                    )
                )
                # Ищем по полному ФИО — все слова должны присутствовать
                full_name_q = models.Q()
                for word in words:
                    full_name_q &= models.Q(full_name__icontains=word)

                # Также ищем по остальным полям
                other_q = models.Q()
                for word in words:
                    other_q |= models.Q(tab_number__icontains=word)
                    other_q |= models.Q(corporate_email__icontains=word)
                    other_q |= models.Q(personal_email__icontains=word)
                    other_q |= models.Q(department__name__icontains=word)

                qs = qs.filter(full_name_q | other_q).distinct()
            else:
                # Одно слово — ищем по всем полям
                word = words[0]
                qs = qs.filter(
                    models.Q(last_name__icontains=word)
                    | models.Q(first_name__icontains=word)
                    | models.Q(patronymic__icontains=word)
                    | models.Q(tab_number__icontains=word)
                    | models.Q(corporate_email__icontains=word)
                    | models.Q(personal_email__icontains=word)
                    | models.Q(department__name__icontains=word),
                ).distinct()

        if sort in self.SORT_FIELDS:
            field = self.SORT_FIELDS[sort]
            if order == 'desc':
                field = '-' + field
            qs = qs.order_by(field)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_sort'] = self.request.GET.get('sort', 'full_name')
        context['current_order'] = self.request.GET.get('order', 'asc')
        context['show_archived'] = self.request.GET.get('show_archived', '0') == '1'
        context['marked_count'] = User.objects.filter(archive_status=User.STATUS_MARKED).count()
        context['archived_count'] = User.objects.filter(archive_status=User.STATUS_ARCHIVED).count()
        context['admin_count'] = User.objects.filter(is_admin=True).count()
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['current_dept_id'] = self.request.GET.get('dept_id', '')
        context['current_mol'] = self.request.GET.get('mol', '')
        return context

    def post(self, request, *args, **kwargs):
        """Обработка загрузки CSV прямо со страницы списка пользователей."""
        file = request.FILES.get('csv_file')

        if not file:
            messages.error(request, 'Выберите файл для загрузки.')
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return self.render_to_response(context)

        try:
            content = file.read().decode('utf-8-sig')
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
        except Exception as e:
            messages.error(request, f'Ошибка чтения файла: {e}')
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return self.render_to_response(context)

        if not rows:
            messages.error(request, 'Файл пуст.')
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return self.render_to_response(context)

        if rows and rows[0][0].strip().isdigit() is False and '№' in ''.join(rows[0]):
            rows = rows[1:]

        parsed_data = []
        current_dept = None

        for row in rows:
            if not row or len(row) < 2:
                continue
            first_cell = row[0].strip()
            if first_cell and first_cell.isdigit():
                full_name = row[1].strip() if len(row) > 1 else ''
                position_name = row[2].strip() if len(row) > 2 else ''
                if full_name:
                    parsed_data.append((current_dept, full_name, position_name))
            else:
                dept_name = first_cell.strip()
                if dept_name:
                    current_dept = dept_name

        created_users = 0
        updated_users = 0
        archived_users = 0
        skipped_no_dept = 0
        errors = []
        file_names = set()

        with transaction.atomic():
            dept_map = {}

            for dept_name, full_name, position_name in parsed_data:
                if not dept_name:
                    skipped_no_dept += 1
                    continue

                if dept_name not in dept_map:
                    dept, created = Department.objects.get_or_create(
                        name=dept_name,
                        defaults={'is_active': True}
                    )
                    if created:
                        dept_map[dept_name] = dept
                    else:
                        dept.is_active = True
                        dept.save()
                        dept_map[dept_name] = dept

                current_department = dept_map[dept_name]

                position = None
                if position_name:
                    position, created = Position.objects.get_or_create(
                        name=position_name,
                        department=current_department,
                        defaults={'is_active': True}
                    )
                    if not created:
                        position.is_active = True
                        position.save()

                name_parts = full_name.strip().split()
                if len(name_parts) >= 3:
                    last_name, first_name, patronymic = name_parts[0], name_parts[1], ' '.join(name_parts[2:])
                elif len(name_parts) == 2:
                    last_name, first_name = name_parts
                    patronymic = ''
                elif len(name_parts) == 1:
                    last_name = name_parts[0]
                    first_name = ''
                    patronymic = ''
                else:
                    errors.append(f'Некорректное ФИО: {full_name}')
                    continue

                try:
                    user, created = User.objects.get_or_create(
                        last_name=last_name,
                        first_name=first_name,
                        patronymic=patronymic,
                        defaults={
                            'department': current_department,
                            'position': position,
                            'archive_status': User.STATUS_ACTIVE,
                        }
                    )
                    if created:
                        # Новый сотрудник — присваиваем username
                        user.username = f'{last_name}_{first_name}'
                        user.save()
                        created_users += 1
                    else:
                        # Существующий сотрудник — обновляем только подразделение и должность
                        user.department = current_department
                        user.position = position
                        user.archive_status = User.STATUS_ACTIVE
                        user.save()
                        updated_users += 1

                    file_names.add(full_name)
                except Exception as e:
                    errors.append(f'Ошибка при создании {full_name}: {e}')

            existing_users = User.objects.exclude(archive_status=User.STATUS_ARCHIVED)
            for user in existing_users:
                if user.is_admin:
                    continue
                full_name = f'{user.last_name} {user.first_name} {user.patronymic}'.strip()
                if full_name and full_name not in file_names:
                    user.archive_status = User.STATUS_MARKED
                    user.marked_archive_date = timezone.now().date()
                    user.save()
                    archived_users += 1

        self.object_list = self.get_queryset()
        context = self.get_context_data()
        context['import_result'] = {
            'created_users': created_users,
            'updated_users': updated_users,
            'archived_users': archived_users,
            'skipped_no_dept': skipped_no_dept,
            'errors': errors,
        }
        return self.render_to_response(context)


class DepartmentListView(LoginRequiredMixin, ListView):
    """Список подразделений."""
    model = Department
    template_name = 'accounts/department_list.html'
    context_object_name = 'departments'
    paginate_by = 50

    def get_queryset(self):
        return Department.objects.filter(is_active=True).select_related('parent').order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Формируем дерево подразделений
        all_depts = Department.objects.filter(is_active=True).select_related('parent').order_by('name')
        dept_dict = {d.pk: {'obj': d, 'children': [], 'positions': []} for d in all_depts}

        # Группируем должности по подразделениям на основе местоположения сотрудников
        # (а не на основе поля department у должности)
        positions_by_dept = {}
        for dept in all_depts:
            # Находим все должности сотрудников в этом подразделении
            pos_ids = User.objects.filter(
                department=dept,
                archive_status='active',
                position__isnull=False,
            ).values_list('position_id', flat=True).distinct()
            
            positions = []
            for pos_id in pos_ids:
                pos = Position.objects.filter(pk=pos_id, is_active=True).first()
                if pos:
                    pos.employee_count = User.objects.filter(
                        position=pos,
                        archive_status='active',
                        department=dept,
                    ).count()
                    positions.append(pos)
            
            positions.sort(key=lambda p: p.name)
            positions_by_dept[dept.pk] = positions

        # Строим дерево
        roots = []
        for d in all_depts:
            entry = dept_dict[d.pk]
            entry['positions'] = positions_by_dept.get(d.pk, [])
            # Считаем сотрудников для подразделения
            entry['obj'].employee_count = User.objects.filter(
                department=d,
                archive_status='active',
            ).count()
            if d.parent_id and d.parent_id in dept_dict:
                dept_dict[d.parent_id]['children'].append(entry)
            else:
                roots.append(entry)

        context['dept_tree'] = roots
        return context


class PositionListView(LoginRequiredMixin, ListView):
    """Список должностей."""
    model = Position
    template_name = 'accounts/position_list.html'
    context_object_name = 'positions'
    paginate_by = 50

    def get_queryset(self):
        return Position.objects.filter(is_active=True).select_related('department').order_by('name')


class DashboardView(LoginRequiredMixin, TemplateView):
    """Дашборд — главная страница с обзорной статистикой."""
    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from equipment.models import Equipment
        context['users_count'] = User.objects.filter(is_fired=False).count()
        context['departments_count'] = Department.objects.filter(is_active=True).count()
        context['equipment_count'] = Equipment.objects.filter(is_active=True).count()
        context['secured_count'] = Equipment.objects.filter(is_active=True, antivirus_active=True).count()
        return context


class UserGeneralView(LoginRequiredMixin, DetailView):
    """Общая информация о пользователе."""
    model = User
    template_name = 'accounts/user_general.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])


class UserEditContactsView(LoginRequiredMixin, DetailView):
    """Редактирование контактных данных пользователя."""
    model = User
    template_name = 'accounts/user_general.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        user.corporate_email = request.POST.get('corporate_email', '')
        user.personal_email = request.POST.get('personal_email', '')
        user.corporate_phone = request.POST.get('corporate_phone', '')
        user.personal_phone = request.POST.get('personal_phone', '')
        user.save(update_fields=[
            'corporate_email', 'personal_email',
            'corporate_phone', 'personal_phone',
        ])
        messages.success(request, 'Контактные данные обновлены.')
        return redirect('accounts:user_general', pk=user.pk)


class UserEditAdditionalView(LoginRequiredMixin, DetailView):
    """Редактирование дополнительных данных пользователя."""
    model = User
    template_name = 'accounts/user_general.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        user.snils = request.POST.get('snils', '')
        user.domain_account = request.POST.get('domain_account', '')
        user.save(update_fields=['snils', 'domain_account'])
        messages.success(request, 'Дополнительные данные обновлены.')
        return redirect('accounts:user_general', pk=user.pk)


class UserClearMaxIdView(LoginRequiredMixin, DetailView):
    """Очистка MAX ID пользователя."""
    model = User
    template_name = 'accounts/user_general.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        user.max_id = ''
        user.notify_max = False
        user.save(update_fields=['max_id', 'notify_max'])
        messages.success(request, 'MAX ID очищен.')
        return redirect('accounts:user_general', pk=user.pk)


class UserClearTelegramIdView(LoginRequiredMixin, DetailView):
    """Очистка Telegram ID пользователя."""
    model = User
    template_name = 'accounts/user_general.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        user.telegram_id = ''
        user.notify_telegram = False
        user.save(update_fields=['telegram_id', 'notify_telegram'])
        messages.success(request, 'Telegram ID очищен.')
        return redirect('accounts:user_general', pk=user.pk)


class UserNotifySettingsView(LoginRequiredMixin, DetailView):
    """Настройки каналов связи пользователя."""
    model = User
    template_name = 'accounts/user_general.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        user.notify_max = 'notify_max' in request.POST and bool(user.max_id)
        user.notify_telegram = 'notify_telegram' in request.POST and bool(user.telegram_id)
        user.notify_corporate_email = 'notify_corporate_email' in request.POST and bool(user.corporate_email)
        user.notify_personal_email = 'notify_personal_email' in request.POST and bool(user.personal_email)
        user.save(update_fields=[
            'notify_max', 'notify_telegram',
            'notify_corporate_email', 'notify_personal_email',
        ])
        messages.success(request, 'Настройки каналов связи обновлены.')
        return redirect('accounts:user_general', pk=user.pk)


class UserTrainingsView(LoginRequiredMixin, DetailView):
    """Обучения пользователя."""
    model = User
    template_name = 'accounts/user_trainings.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        context['enrollments'] = user.training_enrollments.select_related(
            'training', 'training__training_type', 'training__training_type__category',
        ).order_by('-enrolled_at')
        return context


class UserEquipmentView(LoginRequiredMixin, DetailView):
    """Закрепленное оборудование пользователя."""
    model = User
    template_name = 'accounts/user_equipment.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        context['assigned_equipment'] = user.equipment_assignments.filter(is_active=True).all()
        return context


class UserAccessView(LoginRequiredMixin, DetailView):
    """Доступы пользователя."""
    model = User
    template_name = 'accounts/user_access.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        # Группы и права доступа (Django native)
        context['groups'] = user.groups.all()
        context['permissions'] = user.user_permissions.all()

        # Гранты доступа (кастомная система), разбитые по типам
        grants = user.access_grants.select_related(
            'group', 'group__resource',
        ).filter(is_active=True, revoked_at__isnull=True)
        context['network_grants'] = grants.filter(group__resource__type='network')
        context['software_grants'] = grants.filter(group__resource__type='software')
        context['other_grants'] = grants.exclude(
            group__resource__type__in=['network', 'software'],
        ).exclude(group__resource__isnull=True)

        grant_group_ids = set(grants.values_list('group', flat=True))
        context['grant_group_ids'] = grant_group_ids

        # Группы доступа из ролей должности
        from access.models import AccessGroup
        role_group_ids = set()
        if user.position:
            role_group_ids = set(
                user.position.position_roles.select_related(
                    'role__groups__access_group',
                ).values_list(
                    'role__groups__access_group', flat=True
                ).distinct()
            )
        context['role_group_ids'] = role_group_ids

        context['role_access_groups'] = AccessGroup.objects.filter(
            id__in=role_group_ids
        ).select_related(
            'resource',
        ).order_by('resource__type', 'name')

        # Все группы доступа (из грантов + из ролей), без дубликатов
        all_group_ids = grant_group_ids | role_group_ids
        context['all_access_groups'] = AccessGroup.objects.filter(
            id__in=all_group_ids
        ).select_related(
            'resource',
        ).order_by('resource__type', 'name')
        return context


# ============================================================================
# Редактирование пользователя
# ============================================================================

class UserEditView(LoginRequiredMixin, DetailView):
    """Редактирование профиля пользователя."""
    model = User
    template_name = 'accounts/user_edit.html'
    context_object_name = 'user'

    def get_object(self, queryset=None):
        return User.objects.select_related('department', 'position').get(pk=self.kwargs['pk'])

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = UserEditForm(instance=self.object)
        return render(request, self.template_name, {
            'user': self.object,
            'form': form,
        })

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = UserEditForm(request.POST, instance=self.object)
        if form.is_valid():
            form.save()
            messages.success(request, f'Профиль {self.object.get_full_name()} обновлён.')
            return redirect('accounts:user_general', pk=self.object.pk)
        return render(request, self.template_name, {
            'user': self.object,
            'form': form,
        })


# ============================================================================
# Архивирование пользователя
# ============================================================================

def archive_user(request, pk):
    """Отправить сотрудника в архив."""
    if request.method != 'POST':
        return redirect('accounts:user_list')

    user = get_object_or_404(User, pk=pk)
    user.archive_status = User.STATUS_ARCHIVED
    user.archive_date = timezone.now().date()
    user.save()

    messages.success(request, f'Сотрудник {user.get_full_name()} отправлен в архив.')
    return redirect('accounts:user_list')


# ============================================================================
# Восстановление сотрудника из архива
# ============================================================================

def restore_user(request, pk):
    """Восстановить сотрудника из архива."""
    if request.method != 'POST':
        return redirect('accounts:user_list')

    user = get_object_or_404(User, pk=pk, archive_status=User.STATUS_ARCHIVED)
    user.archive_status = User.STATUS_ACTIVE
    user.archive_date = None
    user.save()

    messages.success(request, f'Сотрудник {user.get_full_name()} восстановлен.')
    return redirect('accounts:user_list')