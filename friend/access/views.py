from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, View,
)
from django.db import models
from django import forms

from accounts.models import Department

from .models import (
    Resource, AccessGroup, AccessGrant, AccessRequest, Role, RoleGroup,
    NetworkResourceDetail, SoftwareResourceDetail, RemoteAccessDetail,
    ServerResourceDetail, DatabaseResourceDetail, ApplicationResourceDetail,
    StorageResourceDetail, CloudResourceDetail, HardwareResourceDetail,
)
from .forms import (
    ResourceForm, AccessGroupForm, AccessGrantForm, AccessRequestForm,
    RoleForm, RoleGroupForm,
    NetworkDetailForm, SoftwareDetailForm, RemoteAccessDetailForm,
    ServerDetailForm, DatabaseDetailForm, ApplicationDetailForm,
    StorageDetailForm, CloudDetailForm, HardwareDetailForm,
)


def api_search_groups(request):
    """API endpoint для поиска/списка групп доступа.
    
    Без параметра q — возвращает все не привязанные к ресурсу группы.
    С параметром q — фильтрует по наименованию/описанию.
    """
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'error': 'XHR required'}, status=400)
    
    q = request.GET.get('q', '').strip()
    
    # Базовый запрос: только не привязанные к ресурсу активные группы
    qs = AccessGroup.objects.filter(
        resource__isnull=True,
        is_active=True
    ).select_related('resource')
    
    # Применяем фильтр поиска
    if q and len(q) >= 2:
        qs = qs.filter(
            models.Q(name__icontains=q) | models.Q(description__icontains=q)
        )
    
    groups = qs[:50]
    
    groups_data = []
    for group in groups:
        groups_data.append({
            'id': group.pk,
            'name': group.display_name,
            'description': group.description[:100] if group.description else '',
        })
    
    return JsonResponse({'groups': groups_data})


def api_search_groups_for_role(request, role_pk):
    """API endpoint для поиска групп, доступных для добавления в роль.
    
    Возвращает группы, которые ЕЩЁ НЕ добавлены в указанную роль.
    """
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'error': 'XHR required'}, status=400)
    
    role = get_object_or_404(Role, pk=role_pk)
    q = request.GET.get('q', '').strip()
    
    # Группы, которые УЖЕ есть в роли
    already_in_role = set(role.groups.values_list('access_group_id', flat=True))
    
    # Базовый запрос: все активные группы, которых НЕТ в роли
    qs = AccessGroup.objects.filter(
        ~models.Q(pk__in=already_in_role),
        is_active=True
    ).select_related('resource')
    
    # Применяем фильтр поиска по наименованию ресурса и группы
    if q and len(q) >= 2:
        qs = qs.filter(
            models.Q(name__icontains=q) | models.Q(description__icontains=q)
        )
    
    groups = qs[:50]
    
    groups_data = []
    for group in groups:
        groups_data.append({
            'id': group.pk,
            'name': group.display_name,
            'description': group.description[:100] if group.description else '',
        })
    
    return JsonResponse({'groups': groups_data})


# ============================================================================
# Ресурсы
# ============================================================================

class ResourceListView(LoginRequiredMixin, ListView):
    """Список ресурсов."""
    model = Resource
    template_name = 'access/resource_list.html'
    context_object_name = 'resources'
    paginate_by = 50

    def get_queryset(self):
        qs = Resource.objects.all()
        q = self.request.GET.get('q', '').strip()
        type_filter = self.request.GET.get('type', '').strip()
        dept_filter = self.request.GET.get('dept', '').strip()
        show_archived = self.request.GET.get('show_archived', '0') == '1'

        if not show_archived:
            qs = qs.filter(is_active=True)

        if type_filter:
            qs = qs.filter(type=type_filter)

        if dept_filter:
            qs = qs.filter(owner_id=dept_filter)

        if q:
            qs = qs.filter(
                models.Q(name__icontains=q)
                | models.Q(description__icontains=q)
                | models.Q(cost_center__icontains=q),
            ).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['resource_types'] = Resource.Type.choices
        context['current_type'] = self.request.GET.get('type', '')
        context['current_dept'] = self.request.GET.get('dept', '')
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['resources_count'] = Resource.objects.filter(is_active=True).count()
        context['show_archived'] = self.request.GET.get('show_archived', '0') == '1'
        # Стартовый индекс для нумерации строк
        page = context['page_obj'].number
        per_page = context['page_obj'].paginator.per_page
        context['start_index'] = (page - 1) * per_page
        return context


class ResourceDetailView(LoginRequiredMixin, DetailView):
    """Детальная страница ресурса."""
    model = Resource
    template_name = 'access/resource_detail.html'
    context_object_name = 'resource'

    def get_queryset(self):
        return Resource.objects.all()


class ResourceCreateView(LoginRequiredMixin, CreateView):
    """Создание ресурса."""
    model = Resource
    form_class = ResourceForm
    template_name = 'access/resource_form.html'
    success_url = reverse_lazy('access:resource_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detail_forms'] = self._get_all_detail_forms()
        context['attached_groups_data'] = '[]'
        return context

    def _get_all_detail_forms(self):
        """Возвращает список всех detail-форм для отображения в шаблоне."""
        detail_map = [
            (NetworkResourceDetail, 'network', 'Сетевой ресурс'),
            (SoftwareResourceDetail, 'software', 'Программное обеспечение'),
            (RemoteAccessDetail, 'remote_access_detail', 'remote', 'Удалённый доступ'),
            (ServerResourceDetail, 'server', 'Сервер'),
            (DatabaseResourceDetail, 'database', 'База данных'),
            (ApplicationResourceDetail, 'application', 'Приложение / Веб-сервис'),
            (StorageResourceDetail, 'storage', 'Хранилище'),
            (CloudResourceDetail, 'cloud', 'Облачный ресурс'),
            (HardwareResourceDetail, 'hardware', 'Оборудование'),
        ]
        result = []
        for model_cls, type_key, type_label in detail_map:
            form_cls = self._create_detail_form(model_cls)
            result.append((
                form_cls(prefix=type_key),
                type_key,
                type_label,
            ))
        return result

    def _create_detail_form(self, model_cls):
        """Создаёт форму для detail-модели с Bootstrap-виджетами."""
        fields = [f.name for f in model_cls._meta.get_fields() if f.name != 'id' and f.name != 'resource_id']
        widgets = {}
        for field_name in fields:
            field = model_cls._meta.get_field(field_name)
            if field_name == 'resource':
                continue
            if isinstance(field, (models.IntegerField, models.PositiveIntegerField)):
                widgets[field_name] = forms.NumberInput(attrs={'class': 'form-control form-control-lg'})
            elif isinstance(field, models.BooleanField):
                widgets[field_name] = forms.CheckboxInput(attrs={'class': 'form-check-input form-check-input-lg'})
            elif isinstance(field, models.DateField):
                widgets[field_name] = forms.DateInput(attrs={'class': 'form-control form-control-lg', 'type': 'date'})
            elif isinstance(field, models.GenericIPAddressField):
                widgets[field_name] = forms.TextInput(attrs={'class': 'form-control form-control-lg'})
            elif isinstance(field, (models.CharField, models.TextField)):
                widgets[field_name] = forms.TextInput(attrs={'class': 'form-control form-control-lg'})
            else:
                widgets[field_name] = forms.TextInput(attrs={'class': 'form-control form-control-lg'})
        return type(
            f'{model_cls.__name__}Form',
            (forms.ModelForm,),
            {
                'Meta': type('Meta', (), {'model': model_cls, 'fields': fields}),
                'widgets': widgets,
            }
        )

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        resource_type = request.POST.get('type', '')

        if form.is_valid():
            resource = form.save()

            detail_map = [
                (NetworkDetailForm, Resource.Type.NETWORK),
                (SoftwareDetailForm, Resource.Type.SOFTWARE),
                (RemoteAccessDetailForm, Resource.Type.REMOTE),
                (ServerDetailForm, Resource.Type.SERVER),
                (DatabaseDetailForm, Resource.Type.DATABASE),
                (ApplicationDetailForm, Resource.Type.APPLICATION),
                (StorageDetailForm, Resource.Type.STORAGE),
                (CloudDetailForm, Resource.Type.CLOUD),
                (HardwareDetailForm, Resource.Type.HARDWARE),
            ]

            for detail_cls, type_key in detail_map:
                if type_key == resource_type:
                    detail_form = detail_cls(request.POST)
                    if detail_form.is_valid():
                        detail = detail_form.save(commit=False)
                        detail.resource = resource
                        detail.save()
                    break

            messages.success(self.request, 'Ресурс создан.')
            return redirect('access:resource_list')

        return render(request, self.template_name, {
            'form': form,
            'detail_forms': self._get_all_detail_forms(),
        })


class ResourceUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование ресурса."""
    model = Resource
    form_class = ResourceForm
    template_name = 'access/resource_form.html'
    success_url = reverse_lazy('access:resource_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detail_forms'] = self._get_all_detail_forms()
        context['attached_groups_data'] = self._get_attached_groups_json()
        return context

    def _get_all_detail_forms(self):
        """Возвращает список всех detail-форм для отображения в шаблоне."""
        resource = self.object
        detail_map = [
            (NetworkResourceDetail, 'network_detail', 'network', 'Сетевой ресурс'),
            (SoftwareResourceDetail, 'software_detail', 'software', 'Программное обеспечение'),
            (RemoteAccessDetail, 'remote_access_detail', 'remote', 'Удалённый доступ'),
            (ServerResourceDetail, 'server_detail', 'server', 'Сервер'),
            (DatabaseResourceDetail, 'database_detail', 'database', 'База данных'),
            (ApplicationResourceDetail, 'application_detail', 'application', 'Приложение / Веб-сервис'),
            (StorageResourceDetail, 'storage_detail', 'storage', 'Хранилище'),
            (CloudResourceDetail, 'cloud_detail', 'cloud', 'Облачный ресурс'),
            (HardwareResourceDetail, 'hardware_detail', 'hardware', 'Оборудование'),
        ]
        result = []
        for model_cls, attr_name, type_key, type_label in detail_map:
            try:
                detail_obj = getattr(resource, attr_name.replace('_detail', ''), None)
                if detail_obj is None:
                    detail_obj = getattr(resource, attr_name)
            except Exception:
                detail_obj = None
            form_cls = self._create_detail_form(model_cls)
            result.append((
                form_cls(instance=detail_obj, prefix=type_key),
                type_key,
                type_label,
            ))
        return result

    def _create_detail_form(self, model_cls):
        """Создаёт форму для detail-модели с Bootstrap-виджетами."""
        fields = [f.name for f in model_cls._meta.get_fields() if f.name != 'id' and f.name != 'resource_id']
        widgets = {}
        for field_name in fields:
            field = model_cls._meta.get_field(field_name)
            if field_name == 'resource':
                continue
            if isinstance(field, (models.IntegerField, models.PositiveIntegerField)):
                widgets[field_name] = forms.NumberInput(attrs={'class': 'form-control form-control-lg'})
            elif isinstance(field, models.BooleanField):
                widgets[field_name] = forms.CheckboxInput(attrs={'class': 'form-check-input form-check-input-lg'})
            elif isinstance(field, models.DateField):
                widgets[field_name] = forms.DateInput(attrs={'class': 'form-control form-control-lg', 'type': 'date'})
            elif isinstance(field, models.GenericIPAddressField):
                widgets[field_name] = forms.TextInput(attrs={'class': 'form-control form-control-lg'})
            elif isinstance(field, (models.CharField, models.TextField)):
                widgets[field_name] = forms.TextInput(attrs={'class': 'form-control form-control-lg'})
            else:
                widgets[field_name] = forms.TextInput(attrs={'class': 'form-control form-control-lg'})
        return type(
            f'{model_cls.__name__}Form',
            (forms.ModelForm,),
            {
                'Meta': type('Meta', (), {'model': model_cls, 'fields': fields}),
                'widgets': widgets,
            }
        )

    def _get_attached_groups_json(self):
        """Возвращает JSON с прикреплёнными группами для редактирования."""
        resource = self.object
        groups = resource.grants.filter(grant_type='group', is_active=True).values_list('group_id', 'group__name')
        return [{'id': g[0], 'name': g[1]} for g in groups]

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        resource = self.get_object()
        resource_type = request.POST.get('type', resource.type)

        if form.is_valid():
            form.save()

            detail_map = [
                (NetworkResourceDetail, Resource.Type.NETWORK),
                (SoftwareResourceDetail, Resource.Type.SOFTWARE),
                (RemoteAccessDetail, Resource.Type.REMOTE),
                (ServerResourceDetail, Resource.Type.SERVER),
                (DatabaseResourceDetail, Resource.Type.DATABASE),
                (ApplicationResourceDetail, Resource.Type.APPLICATION),
                (StorageResourceDetail, Resource.Type.STORAGE),
                (CloudResourceDetail, Resource.Type.CLOUD),
                (HardwareResourceDetail, Resource.Type.HARDWARE),
            ]

            for detail_model, type_key in detail_map:
                if type_key == resource_type:
                    # Создаём динамическую форму
                    form_cls = type(
                        f'{detail_model.__name__}Form',
                        (forms.ModelForm,),
                        {'Meta': type('Meta', (), {'model': detail_model, 'fields': '__all__'})}
                    )
                    try:
                        detail_obj = getattr(resource, detail_model.__name__.lower().replace('eresource', 'resource').replace('detail', '_detail'), None)
                        if detail_obj is None:
                            detail_obj = getattr(resource, detail_model.__name__.lower().replace('detail', '_detail'), None)
                    except Exception:
                        detail_obj = None

                    detail_form = form_cls(request.POST, instance=detail_obj, prefix=resource_type)
                    if detail_form.is_valid():
                        detail = detail_form.save(commit=False)
                        detail.resource = resource
                        detail.save()
                    break

            messages.success(self.request, 'Ресурс обновлён.')
            return redirect('access:resource_list')

        return render(request, self.template_name, {
            'form': form,
            'detail_forms': self._get_all_detail_forms(),
            'attached_groups_data': self._get_attached_groups_json(),
        })


class ResourceDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление ресурса."""
    model = Resource
    success_url = reverse_lazy('access:resource_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Ресурс удалён.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# Группы доступа
# ============================================================================

class AccessGroupListView(LoginRequiredMixin, ListView):
    """Список групп доступа."""
    model = AccessGroup
    template_name = 'access/group_list.html'
    context_object_name = 'groups'
    paginate_by = 50

    def get_queryset(self):
        qs = AccessGroup.objects.select_related('resource', 'pinned_department').all()
        q = self.request.GET.get('q', '').strip()
        show_archived = self.request.GET.get('show_archived', '0') == '1'
        audited_filter = self.request.GET.get('audited', '').strip()
        ad_link_filter = self.request.GET.get('ad_link', '').strip()

        if not show_archived:
            qs = qs.filter(is_active=True)

        if audited_filter == '1':
            qs = qs.filter(audited=True)
        elif audited_filter == '0':
            qs = qs.filter(audited=False)

        if ad_link_filter == '1':
            qs = qs.filter(~models.Q(ad_group_dn=''))
        elif ad_link_filter == '0':
            qs = qs.filter(ad_group_dn='')

        if q:
            qs = qs.filter(
                models.Q(name__icontains=q)
                | models.Q(description__icontains=q)
                | models.Q(resource_name__icontains=q),
            ).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['groups_count'] = AccessGroup.objects.filter(is_active=True).count()
        context['current_audited'] = self.request.GET.get('audited', '')
        context['current_ad_link'] = self.request.GET.get('ad_link', '')
        # Стартовый индекс для нумерации строк
        page = context['page_obj'].number
        per_page = context['page_obj'].paginator.per_page
        context['start_index'] = (page - 1) * per_page
        return context


class AccessGroupDetailView(LoginRequiredMixin, DetailView):
    """Детальная страница группы доступа."""
    model = AccessGroup
    template_name = 'access/group_detail.html'
    context_object_name = 'group'

    def get_queryset(self):
        return AccessGroup.objects.all()


class AccessGroupCreateView(LoginRequiredMixin, CreateView):
    """Создание группы доступа."""
    model = AccessGroup
    form_class = AccessGroupForm
    template_name = 'access/group_form.html'
    success_url = reverse_lazy('access:group_list')

    def form_valid(self, form):
        messages.success(self.request, 'Группа доступа создана.')
        return super().form_valid(form)


class AccessGroupUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование группы доступа."""
    model = AccessGroup
    form_class = AccessGroupForm
    template_name = 'access/group_form.html'
    success_url = reverse_lazy('access:group_list')

    def form_valid(self, form):
        messages.success(self.request, 'Группа доступа обновлена.')
        return super().form_valid(form)


class AccessGroupDeleteView(LoginRequiredMixin, DeleteView):
    """Архивирование группы доступа (soft delete)."""
    model = AccessGroup
    success_url = reverse_lazy('access:group_list')
    template_name = 'access/accessgroup_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.is_active = False
        obj.save()
        messages.success(request, 'Группа доступа архивирована.')
        return redirect(self.success_url)


class AccessGroupRestoreView(LoginRequiredMixin, View):
    """Восстановление группы из архива."""

    def post(self, request, *args, **kwargs):
        obj = get_object_or_404(AccessGroup, pk=kwargs['pk'])
        obj.is_active = True
        obj.save()
        messages.success(request, 'Группа доступа восстановлена.')
        return redirect('access:group_list')


# ============================================================================
# Гранты доступа
# ============================================================================

class GrantListView(LoginRequiredMixin, ListView):
    """Список грантов доступа."""
    model = AccessGrant
    template_name = 'access/grant_list.html'
    context_object_name = 'grants'
    paginate_by = 50

    def get_queryset(self):
        qs = AccessGrant.objects.select_related('resource', 'user', 'group', 'granted_by').all()
        q = self.request.GET.get('q', '').strip()
        level_filter = self.request.GET.get('level', '').strip()
        grant_type_filter = self.request.GET.get('grant_type', '').strip()
        show_archived = self.request.GET.get('show_archived', '0') == '1'

        if not show_archived:
            qs = qs.filter(is_active=True)

        if level_filter:
            qs = qs.filter(level=level_filter)

        if grant_type_filter:
            qs = qs.filter(grant_type=grant_type_filter)

        if q:
            qs = qs.filter(
                models.Q(resource__name__icontains=q)
                | models.Q(user__last_name__icontains=q)
                | models.Q(user__first_name__icontains=q)
                | models.Q(group__name__icontains=q),
            ).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grant_levels'] = AccessGrant.Level.choices
        context['current_level'] = self.request.GET.get('level', '')
        context['current_grant_type'] = self.request.GET.get('grant_type', '')
        context['grants_count'] = AccessGrant.objects.filter(is_active=True).count()
        return context


class GrantCreateView(LoginRequiredMixin, CreateView):
    """Создание гранта доступа."""
    model = AccessGrant
    form_class = AccessGrantForm
    template_name = 'access/grant_form.html'
    success_url = reverse_lazy('access:grant_list')

    def form_valid(self, form):
        messages.success(self.request, 'Грант доступа создан.')
        return super().form_valid(form)


class GrantDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление гранта доступа."""
    model = AccessGrant
    success_url = reverse_lazy('access:grant_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Грант доступа удалён.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# Заявки на доступ
# ============================================================================

class AccessRequestListView(LoginRequiredMixin, ListView):
    """Список заявок на доступ."""
    model = AccessRequest
    template_name = 'access/request_list.html'
    context_object_name = 'requests'
    paginate_by = 50

    def get_queryset(self):
        qs = AccessRequest.objects.select_related('requester', 'resource', 'approver').all()
        q = self.request.GET.get('q', '').strip()
        status_filter = self.request.GET.get('status', '').strip()

        if status_filter:
            qs = qs.filter(status=status_filter)

        if q:
            qs = qs.filter(
                models.Q(requester__last_name__icontains=q)
                | models.Q(requester__first_name__icontains=q)
                | models.Q(resource__name__icontains=q)
                | models.Q(justification__icontains=q),
            ).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = AccessRequest.Status.choices
        context['current_status'] = self.request.GET.get('status', '')
        return context


class AccessRequestCreateView(LoginRequiredMixin, CreateView):
    """Создание заявки на доступ."""
    model = AccessRequest
    form_class = AccessRequestForm
    template_name = 'access/request_form.html'
    success_url = reverse_lazy('access:request_list')

    def form_valid(self, form):
        form.instance.requester = self.request.user
        messages.success(self.request, 'Заявка на доступ создана.')
        return super().form_valid(form)


class AccessRequestDetailView(LoginRequiredMixin, DetailView):
    """Детальная страница заявки."""
    model = AccessRequest
    template_name = 'access/request_detail.html'
    context_object_name = 'request'

    def get_queryset(self):
        return AccessRequest.objects.select_related('requester', 'resource', 'approver', 'grant')

    def post(self, request, *args, **kwargs):
        request_obj = self.get_object()
        action = request.POST.get('action')

        if action == 'approve':
            request_obj.approve(self.request.user)
            messages.success(request, 'Заявка согласована.')
        elif action == 'grant':
            request_obj.grant_access(self.request.user)
            messages.success(request, 'Доступ выдан.')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            request_obj.reject(reason)
            messages.success(request, 'Заявка отклонена.')

        return redirect('access:request_detail', pk=request_obj.pk)


class AccessRequestUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование заявки."""
    model = AccessRequest
    form_class = AccessRequestForm
    template_name = 'access/request_form.html'
    success_url = reverse_lazy('access:request_list')

    def form_valid(self, form):
        messages.success(self.request, 'Заявка обновлена.')
        return super().form_valid(form)


# ============================================================================
# Роли
# ============================================================================

class RoleListView(LoginRequiredMixin, ListView):
    """Список ролей."""
    model = Role
    template_name = 'access/role_list.html'
    context_object_name = 'roles'
    paginate_by = 50

    def get_queryset(self):
        qs = Role.objects.all()
        q = self.request.GET.get('q', '').strip()
        show_archived = self.request.GET.get('show_archived', '0') == '1'

        if not show_archived:
            qs = qs.filter(is_active=True)

        if q:
            qs = qs.filter(
                models.Q(name__icontains=q)
                | models.Q(description__icontains=q),
            ).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles_count'] = Role.objects.filter(is_active=True).count()
        return context


class RoleDetailView(LoginRequiredMixin, DetailView):
    """Детальная страница роли."""
    model = Role
    template_name = 'access/role_detail.html'
    context_object_name = 'role'

    def get_queryset(self):
        return Role.objects.all()


class RoleCreateView(LoginRequiredMixin, CreateView):
    """Создание роли."""
    model = Role
    form_class = RoleForm
    template_name = 'access/role_form.html'
    success_url = reverse_lazy('access:role_list')

    def form_valid(self, form):
        messages.success(self.request, 'Роль создана.')
        return super().form_valid(form)


class RoleUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование роли."""
    model = Role
    form_class = RoleForm
    template_name = 'access/role_form.html'
    success_url = reverse_lazy('access:role_list')

    def form_valid(self, form):
        messages.success(self.request, 'Роль обновлена.')
        return super().form_valid(form)


class RoleDeleteView(LoginRequiredMixin, DeleteView):
    """Архивирование роли (soft delete)."""
    model = Role
    success_url = reverse_lazy('access:role_list')
    template_name = 'access/role_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.is_active = False
        obj.save()
        messages.success(request, 'Роль архивирована.')
        return redirect(self.success_url)


class RoleRestoreView(LoginRequiredMixin, View):
    """Восстановление роли из архива."""

    def post(self, request, *args, **kwargs):
        obj = get_object_or_404(Role, pk=kwargs['pk'])
        obj.is_active = True
        obj.save()
        messages.success(request, 'Роль восстановлена.')
        return redirect('access:role_list')


class RoleGroupAddView(LoginRequiredMixin, View):
    """Добавление группы в роль."""

    def post(self, request, *args, **kwargs):
        role = get_object_or_404(Role, pk=kwargs['pk'])
        group_id = request.POST.get('access_group')
        
        if group_id:
            from .models import AccessGroup
            group = get_object_or_404(AccessGroup, pk=group_id)
            # Проверяем, что группа ещё не добавлена
            if not RoleGroup.objects.filter(role=role, access_group=group).exists():
                RoleGroup.objects.create(role=role, access_group=group, added_by=request.user)
                messages.success(request, 'Группа добавлена в роль.')
            else:
                messages.warning(request, 'Группа уже добавлена в роль.')
        
        return redirect('access:role_detail', pk=role.pk)


class RoleGroupDeleteView(LoginRequiredMixin, View):
    """Удаление группы из роли."""

    def post(self, request, *args, **kwargs):
        role = get_object_or_404(Role, pk=kwargs['role_pk'])
        group_id = request.POST.get('group_id')
        
        if group_id:
            RoleGroup.objects.filter(role=role, access_group_id=group_id).delete()
            messages.success(request, 'Группа удалена из роли.')
        
        return redirect('access:role_detail', pk=role.pk)
