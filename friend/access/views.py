from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, View,
)
from django.db import models
from django import forms

from accounts.models import Department, Position, User

from .models import (
    Resource, AccessGroup, AccessGrant, AccessRequest, Role, RoleGroup,
    GroupContainer, RoleGroupContainer, GroupContainerGroup, PositionRole,
    NetworkResourceDetail, SoftwareResourceDetail, RemoteAccessDetail,
    ServerResourceDetail, DatabaseResourceDetail, ApplicationResourceDetail,
    StorageResourceDetail, CloudResourceDetail, HardwareResourceDetail,
    Organization, Contract, ExternalUser,
)
from .forms import (
    ResourceForm, AccessGroupForm, AccessGrantForm, ExternalAccessGrantForm, AccessRequestForm,
    RoleForm, RoleGroupForm, GroupContainerForm, RoleGroupContainerForm, GroupContainerGroupForm,
    NetworkDetailForm, SoftwareDetailForm, RemoteAccessDetailForm,
    ServerDetailForm, DatabaseDetailForm, ApplicationDetailForm,
    StorageDetailForm, CloudDetailForm, HardwareDetailForm,
    OrganizationForm, ContractForm, ExternalUserForm,
)


def api_search_groups(request):
    """API endpoint для поиска/списка групп доступа.
    
    Возвращает активные группы, фильтруя по наименованию/описанию если передан q.
    """
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'error': 'XHR required'}, status=400)
    
    q = request.GET.get('q', '').strip()
    
    # Базовый запрос: только активные группы
    qs = AccessGroup.objects.filter(
        is_active=True
    ).select_related('resource')
    
    # Применяем фильтр поиска
    if q and len(q) >= 2:
        qs = qs.filter(
            models.Q(name__icontains=q) | models.Q(description__icontains=q)
        )
    
    groups = qs[:20]
    
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


def api_search_containers(request):
    """API endpoint для поиска контейнеров групп доступа."""
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'error': 'XHR required'}, status=400)
    
    q = request.GET.get('q', '').strip()
    
    qs = GroupContainer.objects.filter(is_active=True)
    
    if q and len(q) >= 2:
        qs = qs.filter(
            models.Q(name__icontains=q) | models.Q(description__icontains=q)
        )
    
    containers = qs[:50]
    
    containers_data = []
    for container in containers:
        containers_data.append({
            'id': container.pk,
            'name': container.name,
            'description': container.description[:100] if container.description else '',
            'groups_count': container.groups_count,
        })
    
    return JsonResponse({'containers': containers_data})


def api_search_users(request):
    """API endpoint для поиска пользователей."""
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'error': 'XHR required'}, status=400)
    
    q = request.GET.get('q', '').strip()
    
    qs = User.objects.filter(is_active=True)
    
    if q and len(q) >= 2:
        qs = qs.filter(
            models.Q(last_name__icontains=q)
            | models.Q(first_name__icontains=q)
            | models.Q(patronymic__icontains=q)
            | models.Q(tab_number__icontains=q)
            | models.Q(username__icontains=q),
        )
    
    users = qs[:20]
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.pk,
            'full_name': user.get_full_name(),
            'username': user.username,
            'tab_number': user.tab_number or '—',
            'department': user.department.name if user.department else '—',
        })
    
    return JsonResponse({'users': users_data})


def api_search_external_users(request):
    """API endpoint для поиска внешних лиц."""
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'error': 'XHR required'}, status=400)
    
    q = request.GET.get('q', '').strip()
    
    qs = ExternalUser.objects.filter(is_active=True).select_related('contract', 'contract__organization')
    
    if q and len(q) >= 2:
        qs = qs.filter(
            models.Q(full_name__icontains=q)
            | models.Q(position__icontains=q)
            | models.Q(department__icontains=q),
        )
    
    external_users = qs[:20]
    
    users_data = []
    for eu in external_users:
        org_name = eu.contract.organization.name if eu.contract and eu.contract.organization else '—'
        users_data.append({
            'id': eu.pk,
            'full_name': eu.full_name,
            'position': eu.position or '—',
            'department': eu.department or '—',
            'organization': org_name,
            'contract': f"{eu.contract.number} от {eu.contract.date_from.strftime('%d.%m.%Y')}" if eu.contract else '—',
        })
    
    return JsonResponse({'external_users': users_data})


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
        qs = Resource.objects.annotate(
            groups_count=models.Count('access_groups', distinct=True)
        )
        q = self.request.GET.get('q', '').strip()
        type_filter = self.request.GET.get('type', '').strip()
        dept_filter = self.request.GET.get('dept', '').strip()
        groups_filter = self.request.GET.get('groups', '').strip()
        audit_filter = self.request.GET.get('audit', '').strip()
        show_archived = self.request.GET.get('show_archived', '0') == '1'

        if not show_archived:
            qs = qs.filter(is_active=True)

        if type_filter:
            qs = qs.filter(type=type_filter)

        if dept_filter:
            qs = qs.filter(owner_id=dept_filter)

        if groups_filter:
            if groups_filter == '0':
                qs = qs.filter(groups_count=0)
            elif groups_filter == '1':
                qs = qs.filter(groups_count=1)
            elif groups_filter == 'gt1':
                qs = qs.filter(groups_count__gt=1)
            elif groups_filter == 'gt5':
                qs = qs.filter(groups_count__gt=5)

        if audit_filter:
            six_months_ago = timezone.now().date()
            from datetime import timedelta
            six_months_ago = six_months_ago - timedelta(days=183)
            if audit_filter == 'valid':
                qs = qs.filter(last_audit_date__gte=six_months_ago)
            elif audit_filter == 'invalid':
                qs = qs.filter(
                    models.Q(last_audit_date__lt=six_months_ago) | models.Q(last_audit_date__isnull=True)
                )

        if q:
            qs = qs.filter(
                models.Q(name__icontains=q)
                | models.Q(description__icontains=q),
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['resource_types'] = Resource.Type.choices
        context['current_type'] = self.request.GET.get('type', '')
        context['current_dept'] = self.request.GET.get('dept', '')
        context['current_groups'] = self.request.GET.get('groups', '')
        context['current_audit'] = self.request.GET.get('audit', '')
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Группы, которые ЕЩЁ НЕ привязаны к этому ресурсу
        attached_ids = list(
            AccessGroup.objects.filter(resource=self.object).values_list('id', flat=True)
        )
        context['available_groups'] = AccessGroup.objects.exclude(
            id__in=attached_ids
        ).order_by('name')
        return context


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
        groups = AccessGroup.objects.filter(resource=resource, is_active=True).values_list('id', 'name')
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


class ResourceDetachGroupView(LoginRequiredMixin, View):
    """Отвязка группы от ресурса."""

    def post(self, request, *args, **kwargs):
        resource = get_object_or_404(Resource, pk=kwargs['resource_pk'])
        group = get_object_or_404(AccessGroup, pk=kwargs['group_id'])
        
        # Отвязываем группу от ресурса
        group.resource = None
        group.save(update_fields=['resource'])
        
        messages.success(request, f'Группа "{group.display_name}" отвязана от ресурса "{resource.name}".')
        return redirect('access:resource_detail', pk=resource.pk)


class ResourceAttachGroupView(LoginRequiredMixin, View):
    """Привязка группы к ресурсу."""

    def post(self, request, *args, **kwargs):
        resource = get_object_or_404(Resource, pk=kwargs['resource_pk'])
        group_id = request.POST.get('group_id')
        group = get_object_or_404(AccessGroup, pk=group_id)
        
        # Привязываем группу к ресурсу
        group.resource = resource
        group.save(update_fields=['resource'])
        
        messages.success(request, f'Группа "{group.display_name}" привязана к ресурсу "{resource.name}".')
        return redirect('access:resource_detail', pk=resource.pk)


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


class AccessGroupExportCsvView(LoginRequiredMixin, View):
    """Выгрузка групп доступа в CSV."""

    def get(self, request, *args, **kwargs):
        import csv
        import io
        from django.http import HttpResponse

        qs = AccessGroup.objects.select_related('resource', 'pinned_department').all()
        q = request.GET.get('q', '').strip()
        show_archived = request.GET.get('show_archived', '0') == '1'
        audited_filter = request.GET.get('audited', '').strip()
        ad_link_filter = request.GET.get('ad_link', '').strip()

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

        qs = qs.order_by('name')

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['Наименование', 'Старое наименование', 'Описание', 'Ресурс', 'Тип ресурса', 'Подразделение', 'Статус', 'Аудит', 'AD DN', 'Грантов'])

        for group in qs:
            writer.writerow([
                group.name,
                group.old_name or '—',
                group.description or '—',
                group.resource.name if group.resource else '—',
                group.resource.get_type_display() if group.resource else '—',
                group.pinned_department.name if group.pinned_department else '—',
                'Активна' if group.is_active else 'Неактивна',
                'Да' if group.audited else 'Нет',
                group.ad_group_dn or '—',
                group.grants_count,
            ])

        csv_bytes = output.getvalue().encode('utf-8-sig')
        response = HttpResponse(csv_bytes, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=access_groups.csv'
        return response


class AccessGroupDetailView(LoginRequiredMixin, DetailView):
    """Детальная страница группы доступа."""
    model = AccessGroup
    template_name = 'access/group_detail.html'
    context_object_name = 'group'

    def get_queryset(self):
        return AccessGroup.objects.prefetch_related(
            'grants',
            'grants__user',
            'grants__external_user',
            'grants__granted_by',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.get_object()
        # Separate active and inactive grants
        context['active_grants'] = group.grants.filter(is_active=True).order_by('-granted_at')
        context['archived_grants'] = group.grants.filter(is_active=False).order_by('-granted_at')
        return context


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
        qs = AccessGrant.objects.select_related('user', 'group', 'group__resource', 'granted_by').filter(grant_type='user')
        show_archived = 'show_archived' in self.request.GET

        if not show_archived:
            qs = qs.filter(is_active=True)

        # Поиск по ФИО пользователя
        user_q = self.request.GET.get('user_q', '').strip()
        if user_q:
            words = user_q.split()
            user_q_filter = models.Q()
            for word in words:
                user_q_filter &= (
                    models.Q(user__last_name__icontains=word)
                    | models.Q(user__first_name__icontains=word)
                    | models.Q(user__patronymic__icontains=word)
                    | models.Q(user__username__icontains=word)
                )
            qs = qs.filter(user_q_filter)

        # Поиск по группе
        group_q = self.request.GET.get('group_q', '').strip()
        if group_q:
            qs = qs.filter(group__name__icontains=group_q)

        # Фильтр по типу ресурса
        resource_type = self.request.GET.get('resource_type', '').strip()
        if resource_type:
            qs = qs.filter(group__resource__type=resource_type)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grants_count'] = AccessGrant.objects.filter(grant_type='user', is_active=True).count()
        context['current_user_q'] = self.request.GET.get('user_q', '')
        context['current_group_q'] = self.request.GET.get('group_q', '')
        context['current_resource_type'] = self.request.GET.get('resource_type', '')
        context['resource_types'] = Resource.objects.filter(is_active=True).values_list('type', 'type').distinct().order_by('type')
        return context


class GrantCreateView(LoginRequiredMixin, CreateView):
    """Создание гранта доступа (только для пользователей)."""
    model = AccessGrant
    form_class = AccessGrantForm
    template_name = 'access/grant_form.html'
    success_url = reverse_lazy('access:grant_list')

    def get_initial(self):
        initial = super().get_initial()
        if 'group' in self.request.GET:
            initial['group'] = self.request.GET['group']
        return initial

    def form_valid(self, form):
        form.instance.grant_type = 'user'
        form.instance.granted_by = self.request.user
        messages.success(self.request, 'Грант доступа создан.')
        return super().form_valid(form)


class GrantDeleteView(LoginRequiredMixin, View):
    """Архивирование гранта доступа."""

    def post(self, request, *args, **kwargs):
        grant = get_object_or_404(AccessGrant, pk=kwargs['pk'])
        grant.is_active = False
        grant.save()
        messages.success(request, 'Грант доступа архивирован.')
        return redirect('access:group_detail', pk=grant.group.pk)


class GrantRestoreView(LoginRequiredMixin, View):
    """Восстановление гранта из архива."""

    def post(self, request, *args, **kwargs):
        grant = get_object_or_404(AccessGrant, pk=kwargs['pk'])
        grant.is_active = True
        grant.save()
        messages.success(request, 'Грант доступа восстановлен.')
        return redirect('access:group_detail', pk=grant.group.pk)


class ExternalGrantListView(LoginRequiredMixin, ListView):
    """Список грантов внешних лиц."""
    model = AccessGrant
    template_name = 'access/external_grant_list.html'
    context_object_name = 'grants'
    paginate_by = 50

    def get_queryset(self):
        qs = AccessGrant.objects.select_related(
            'external_user', 'external_user__contract', 'external_user__contract__organization',
            'group', 'group__resource', 'granted_by'
        ).filter(grant_type='external')
        show_archived = 'show_archived' in self.request.GET

        if not show_archived:
            qs = qs.filter(is_active=True)

        # Поиск по ФИО
        user_q = self.request.GET.get('user_q', '').strip()
        if user_q:
            words = user_q.split()
            user_q_filter = models.Q()
            for word in words:
                user_q_filter &= models.Q(full_name__icontains=word)
            qs = qs.filter(user_q_filter)

        # Фильтр по организации
        org_q = self.request.GET.get('org_q', '').strip()
        if org_q:
            qs = qs.filter(external_user__contract__organization__name__icontains=org_q)

        # Фильтр по договору
        contract_q = self.request.GET.get('contract_q', '').strip()
        if contract_q:
            qs = qs.filter(external_user__contract__number__icontains=contract_q)

        # Фильтр по типу ресурса
        resource_type = self.request.GET.get('resource_type', '').strip()
        if resource_type:
            qs = qs.filter(group__resource__type=resource_type)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grants_count'] = AccessGrant.objects.filter(grant_type='external', is_active=True).count()
        context['current_user_q'] = self.request.GET.get('user_q', '')
        context['current_org_q'] = self.request.GET.get('org_q', '')
        context['current_contract_q'] = self.request.GET.get('contract_q', '')
        context['current_resource_type'] = self.request.GET.get('resource_type', '')
        context['resource_types'] = Resource.objects.filter(is_active=True).values_list('type', 'type').distinct().order_by('type')
        return context




class GrantExportCsvView(LoginRequiredMixin, View):
    """Выгрузка грантов сотрудников в CSV."""

    def get(self, request, *args, **kwargs):
        import csv
        import io
        from django.http import HttpResponse

        qs = AccessGrant.objects.select_related(
            'user', 'group', 'group__resource', 'granted_by'
        ).filter(grant_type='user')

        show_archived = 'show_archived' in request.GET
        if not show_archived:
            qs = qs.filter(is_active=True)

        user_q = request.GET.get('user_q', '').strip()
        if user_q:
            words = user_q.split()
            user_q_filter = models.Q()
            for word in words:
                user_q_filter &= (
                    models.Q(user__last_name__icontains=word)
                    | models.Q(user__first_name__icontains=word)
                    | models.Q(user__patronymic__icontains=word)
                    | models.Q(user__username__icontains=word)
                )
            qs = qs.filter(user_q_filter)

        group_q = request.GET.get('group_q', '').strip()
        if group_q:
            qs = qs.filter(group__name__icontains=group_q)

        resource_type = request.GET.get('resource_type', '').strip()
        if resource_type:
            qs = qs.filter(group__resource__type=resource_type)

        qs = qs.order_by('user__last_name', 'user__first_name', 'group__name')

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow([
            'Тип',
            'ФИО сотрудника',
            'Логин',
            'Группа доступа',
            'Ресурс',
            'Тип ресурса',
            'Подразделение',
            'Статус',
            'Выдан',
            'Истекает',
            'Кем выдан',
            'Обоснование',
        ])

        for grant in qs:
            user = grant.user
            status = 'Активен'
            if grant.is_revoked:
                status = 'Отозван'
            elif grant.is_expired:
                status = 'Просрочен'

            writer.writerow([
                'Сотрудник',
                user.get_full_name() or user.username,
                user.username,
                grant.group.name,
                grant.group.resource.name if grant.group.resource else '—',
                grant.group.resource.get_type_display() if grant.group.resource else '—',
                grant.group.pinned_department.name if grant.group.pinned_department else '—',
                status,
                grant.granted_at.strftime('%d.%m.%Y') if grant.granted_at else '—',
                grant.expires_at.strftime('%d.%m.%Y') if grant.expires_at else '—',
                grant.granted_by.get_full_name() if grant.granted_by else '—',
                grant.justification or '—',
            ])

        csv_bytes = output.getvalue().encode('utf-8-sig')
        response = HttpResponse(csv_bytes, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=grants_employees.csv'
        return response


class ExternalGrantExportCsvView(LoginRequiredMixin, View):
    """Выгрузка грантов внешних лиц в CSV."""

    def get(self, request, *args, **kwargs):
        import csv
        import io
        from django.http import HttpResponse

        qs = AccessGrant.objects.select_related(
            'external_user', 'external_user__contract', 'external_user__contract__organization',
            'group', 'group__resource', 'granted_by'
        ).filter(grant_type='external')

        show_archived = 'show_archived' in request.GET
        if not show_archived:
            qs = qs.filter(is_active=True)

        user_q = request.GET.get('user_q', '').strip()
        if user_q:
            words = user_q.split()
            user_q_filter = models.Q()
            for word in words:
                user_q_filter &= models.Q(full_name__icontains=word)
            qs = qs.filter(user_q_filter)

        org_q = request.GET.get('org_q', '').strip()
        if org_q:
            qs = qs.filter(external_user__contract__organization__name__icontains=org_q)

        contract_q = request.GET.get('contract_q', '').strip()
        if contract_q:
            qs = qs.filter(external_user__contract__number__icontains=contract_q)

        resource_type = request.GET.get('resource_type', '').strip()
        if resource_type:
            qs = qs.filter(group__resource__type=resource_type)

        qs = qs.order_by('external_user__full_name', 'group__name')

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow([
            'Тип',
            'ФИО',
            'Организация',
            'Договор',
            'Должность',
            'Подразделение',
            'Группа доступа',
            'Ресурс',
            'Тип ресурса',
            'Статус',
            'Выдан',
            'Истекает',
            'Кем выдан',
            'Обоснование',
        ])

        for grant in qs:
            ext_user = grant.external_user
            status = 'Активен'
            if grant.is_revoked:
                status = 'Отозван'
            elif grant.is_expired:
                status = 'Просрочен'

            contract = ext_user.contract
            org = contract.organization if contract else None

            writer.writerow([
                'Внешнее лицо',
                ext_user.full_name,
                org.name if org else '—',
                f"{contract.number} от {contract.date.strftime('%d.%m.%Y')}" if contract and contract.date else '—',
                ext_user.position or '—',
                ext_user.department or '—',
                grant.group.name,
                grant.group.resource.name if grant.group.resource else '—',
                grant.group.resource.get_type_display() if grant.group.resource else '—',
                status,
                grant.granted_at.strftime('%d.%m.%Y') if grant.granted_at else '—',
                grant.expires_at.strftime('%d.%m.%Y') if grant.expires_at else '—',
                grant.granted_by.get_full_name() if grant.granted_by else '—',
                grant.justification or '—',
            ])

        csv_bytes = output.getvalue().encode('utf-8-sig')
        response = HttpResponse(csv_bytes, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=grants_external.csv'
        return response


class ExternalGrantCreateView(LoginRequiredMixin, CreateView):
    """Создание гранта доступа внешнему лицу."""
    model = AccessGrant
    form_class = ExternalAccessGrantForm
    template_name = 'access/external_grant_form.html'
    success_url = reverse_lazy('access:external_grant_list')

    def get_initial(self):
        initial = super().get_initial()
        if 'group' in self.request.GET:
            initial['group'] = self.request.GET['group']
        return initial

    def form_valid(self, form):
        form.instance.grant_type = 'external'
        form.instance.granted_by = self.request.user
        messages.success(self.request, 'Грант доступа создан.')
        return super().form_valid(form)


class ExternalGrantDeleteView(LoginRequiredMixin, View):
    """Архивирование гранта доступа внешнего лица."""

    def post(self, request, *args, **kwargs):
        grant = get_object_or_404(AccessGrant, pk=kwargs['pk'])
        grant.is_active = False
        grant.save()
        messages.success(request, 'Грант доступа архивирован.')
        return redirect('access:group_detail', pk=grant.group.pk)


class ExternalGrantRestoreView(LoginRequiredMixin, View):
    """Восстановление гранта из архива."""

    def post(self, request, *args, **kwargs):
        grant = get_object_or_404(AccessGrant, pk=kwargs['pk'])
        grant.is_active = True
        grant.save()
        messages.success(request, 'Грант доступа восстановлен.')
        return redirect('access:group_detail', pk=grant.group.pk)


class GrantImportView(LoginRequiredMixin, View):
    """Импорт грантов из CSV файла."""

    template_name = 'access/grant_import.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            'success_results': [],
            'error_results': [],
        })

    def post(self, request, *args, **kwargs):
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'Выберите CSV файл.')
            return render(request, self.template_name, {
                'success_results': [],
                'error_results': [],
            })

        import csv
        from io import TextIOWrapper
        from accounts.models import User

        success_results = []
        error_results = []

        # Читаем CSV
        try:
            stream = TextIOWrapper(csv_file, encoding='utf-8-sig')
            reader = csv.reader(stream)
            rows = list(reader)
        except Exception as e:
            messages.error(request, f'Ошибка чтения CSV файла: {e}')
            return render(request, self.template_name, {
                'success_results': [],
                'error_results': [],
            })

        if not rows:
            messages.warning(request, 'CSV файл пуст.')
            return render(request, self.template_name, {
                'success_results': [],
                'error_results': [],
            })

        # Пропускаем заголовок
        header = rows[0]
        data_rows = rows[1:]

        for row in data_rows:
            if not row or all(not cell.strip() for cell in row):
                continue

            # Первый столбец — ФИО пользователя
            display_name = row[0].strip() if len(row) > 0 else ''
            # Последний столбец — группы доступа через двоеточие
            groups_str = row[-1].strip() if len(row) > 1 else ''

            if not display_name:
                error_results.append({
                    'row': data_rows.index(row) + 2,
                    'user': '—',
                    'groups': groups_str or '—',
                    'error': 'Отсутствует ФИО пользователя',
                })
                continue

            # Ищем пользователя по ФИО
            user = self._find_user_by_display_name(display_name)
            if not user:
                error_results.append({
                    'row': data_rows.index(row) + 2,
                    'user': display_name,
                    'groups': groups_str or '—',
                    'error': 'Пользователь не найден',
                })
                continue

            # Парсим группы
            if groups_str:
                group_names = [g.strip() for g in groups_str.split(':') if g.strip()]
            else:
                group_names = []

            if not group_names:
                success_results.append({
                    'row': data_rows.index(row) + 2,
                    'user': user.get_full_name(),
                    'groups': '—',
                    'message': 'Нет групп доступа',
                })
                continue

            created_count = 0
            skipped_count = 0
            not_found_groups = []

            for group_name in group_names:
                # Ищем группу доступа по имени
                access_group = AccessGroup.objects.filter(
                    models.Q(name__iexact=group_name) | models.Q(old_name__iexact=group_name)
                ).first()

                if not access_group:
                    not_found_groups.append(group_name)
                    continue

                # Проверяем, нет ли уже активного гранта
                if AccessGrant.objects.filter(
                    user=user,
                    group=access_group,
                    is_active=True,
                ).exists():
                    skipped_count += 1
                    continue

                # Создаём грант
                AccessGrant.objects.create(
                    grant_type='user',
                    user=user,
                    group=access_group,
                    granted_by=request.user,
                )
                created_count += 1

            # Формируем результат
            if created_count > 0 or skipped_count > 0:
                success_results.append({
                    'row': data_rows.index(row) + 2,
                    'user': user.get_full_name(),
                    'groups': groups_str,
                    'created': created_count,
                    'skipped': skipped_count,
                    'not_found_groups': not_found_groups,
                })
            else:
                error_results.append({
                    'row': data_rows.index(row) + 2,
                    'user': user.get_full_name(),
                    'groups': groups_str,
                    'error': 'Группы не найдены: ' + ', '.join(not_found_groups) if not_found_groups else 'Нет групп',
                })

        # Логирование импорта
        from logging_app.models import LogEntry
        LogEntry.objects.create(
            source='access',
            action=LogEntry.Action.CUSTOM,
            severity='info',
            actor=request.user.get_full_name(),
            actor_type='user',
            target_model='AccessGrant',
            target_id=None,
            target_display='Импорт грантов из CSV',
            summary=f'Импорт грантов: создано {len([s for s in success_results if s.get("created", 0) > 0])} записей, ошибок {len(error_results)}',
            details={
                'total_rows': len(data_rows),
                'success_count': len(success_results),
                'error_count': len(error_results),
                'created_total': sum(s.get('created', 0) for s in success_results),
                'skipped_total': sum(s.get('skipped', 0) for s in success_results),
            },
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        messages.success(
            request,
            f'Импорт завершён: создано {sum(s.get("created", 0) for s in success_results)} грантов, '
            f'пропущено {sum(s.get("skipped", 0) for s in success_results)}, '
            f'ошибок {len(error_results)}'
        )

        return render(request, self.template_name, {
            'success_results': success_results,
            'error_results': error_results,
        })

    def _find_user_by_display_name(self, display_name):
        """Ищет пользователя по полному имени (ФИО)."""
        display_name = display_name.strip()
        if not display_name:
            return None

        # Сначала пробуем найти по username (если DisplayName похож на логин)
        if len(display_name) < 50 and ' ' not in display_name:
            user = User.objects.filter(
                models.Q(username__iexact=display_name) |
                models.Q(corporate_email__iexact=display_name)
            ).first()
            if user:
                return user

        # Разбиваем на части
        parts = display_name.split()
        if len(parts) < 2:
            # Пробуем найти по username или email
            return User.objects.filter(
                models.Q(username__iexact=display_name) |
                models.Q(corporate_email__iexact=display_name)
            ).first()

        last_name = parts[0]
        first_name = parts[1]
        patronymic = ' '.join(parts[2:]) if len(parts) > 2 else ''

        # Ищем по ФИО (без отчества сначала)
        qs = User.objects.filter(
            last_name__iexact=last_name,
            first_name__iexact=first_name,
        )

        # Если есть отчество - ищем с ним
        if patronymic:
            # Пробуем точное совпадение
            user = qs.filter(patronymic__iexact=patronymic).first()
            if user:
                return user
            # Пробуем частичное совпадение (отчество может содержать дополнительные данные)
            user = qs.filter(patronymic__icontains=patronymic).first()
            if user:
                return user

        # Если не нашли с отчеством, пробуем без
        return qs.first()

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class GrantDetailView(LoginRequiredMixin, DetailView):
    """Детальная страница гранта доступа."""
    model = AccessGrant
    template_name = 'access/grant_detail.html'
    context_object_name = 'grant'

    def get_queryset(self):
        return AccessGrant.objects.select_related('user', 'group', 'granted_by')


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
        return Role.objects.prefetch_related('groups', 'group_containers').all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = self.get_object()
        
        # Прямые группы роли (через RoleGroup)
        direct_group_ids = set(
            role.groups.values_list('access_group_id', flat=True)
        )
        
        # Группы из контейнеров роли
        container_group_ids = set()
        for rgc in role.group_containers.select_related('group_container'):
            for group in rgc.group_container.groups.filter(is_active=True):
                container_group_ids.add(group.pk)
        
        # Все группы роли
        all_group_ids = direct_group_ids | container_group_ids
        context['user_groups'] = AccessGroup.objects.filter(
            pk__in=all_group_ids
        ).select_related('resource').order_by('name')
        context['direct_groups_count'] = len(direct_group_ids)
        context['container_groups_count'] = len(container_group_ids)
        context['total_groups_count'] = len(all_group_ids)
        return context


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


# ============================================================================
# Контейнеры групп доступа
# ============================================================================

class GroupContainerListView(LoginRequiredMixin, ListView):
    """Список контейнеров групп доступа."""
    model = GroupContainer
    template_name = 'access/groupcontainer_list.html'
    context_object_name = 'containers'
    paginate_by = 50

    def get_queryset(self):
        qs = GroupContainer.objects.all()
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
        context['containers_count'] = GroupContainer.objects.filter(is_active=True).count()
        return context


class GroupContainerDetailView(LoginRequiredMixin, DetailView):
    """Детальная страница контейнера групп доступа."""
    model = GroupContainer
    template_name = 'access/groupcontainer_detail.html'
    context_object_name = 'container'

    def get_queryset(self):
        return GroupContainer.objects.all()


class GroupContainerCreateView(LoginRequiredMixin, CreateView):
    """Создание контейнера групп доступа."""
    model = GroupContainer
    form_class = GroupContainerForm
    template_name = 'access/groupcontainer_form.html'
    success_url = reverse_lazy('access:container_list')

    def form_valid(self, form):
        messages.success(self.request, 'Контейнер групп создан.')
        return super().form_valid(form)


class GroupContainerUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование контейнера групп доступа."""
    model = GroupContainer
    form_class = GroupContainerForm
    template_name = 'access/groupcontainer_form.html'
    success_url = reverse_lazy('access:container_list')

    def form_valid(self, form):
        messages.success(self.request, 'Контейнер групп обновлён.')
        return super().form_valid(form)


class GroupContainerDeleteView(LoginRequiredMixin, DeleteView):
    """Архивирование контейнера групп (soft delete)."""
    model = GroupContainer
    success_url = reverse_lazy('access:container_list')
    template_name = 'access/groupcontainer_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.is_active = False
        obj.save()
        messages.success(request, 'Контейнер групп архивирован.')
        return redirect(self.success_url)


class GroupContainerRestoreView(LoginRequiredMixin, View):
    """Восстановление контейнера из архива."""

    def post(self, request, *args, **kwargs):
        obj = get_object_or_404(GroupContainer, pk=kwargs['pk'])
        obj.is_active = True
        obj.save()
        messages.success(request, 'Контейнер групп восстановлен.')
        return redirect('access:container_list')


# ============================================================================
# Управление контейнерами в ролях
# ============================================================================

class RoleGroupContainerAddView(LoginRequiredMixin, View):
    """Добавление контейнера групп в роль."""

    def post(self, request, *args, **kwargs):
        role = get_object_or_404(Role, pk=kwargs['pk'])
        container_id = request.POST.get('group_container')
        
        if container_id:
            container = get_object_or_404(GroupContainer, pk=container_id)
            # Проверяем, что контейнер ещё не добавлен
            if not RoleGroupContainer.objects.filter(role=role, group_container=container).exists():
                RoleGroupContainer.objects.create(role=role, group_container=container, added_by=request.user)
                messages.success(request, 'Контейнер групп добавлен в роль.')
            else:
                messages.warning(request, 'Контейнер групп уже добавлен в роль.')
        
        return redirect('access:role_detail', pk=role.pk)


class RoleGroupContainerDeleteView(LoginRequiredMixin, View):
    """Удаление контейнера групп из роли."""

    def post(self, request, *args, **kwargs):
        role = get_object_or_404(Role, pk=kwargs['role_pk'])
        container_id = request.POST.get('container_id')
        
        if container_id:
            RoleGroupContainer.objects.filter(role=role, group_container_id=container_id).delete()
            messages.success(request, 'Контейнер групп удалён из роли.')
        
        return redirect('access:role_detail', pk=role.pk)


# ============================================================================
# Управление группами в контейнерах
# ============================================================================

class GroupContainerGroupAddView(LoginRequiredMixin, View):
    """Добавление группы в контейнер."""

    def post(self, request, *args, **kwargs):
        container = get_object_or_404(GroupContainer, pk=kwargs['pk'])
        group_id = request.POST.get('access_group')
        
        if group_id:
            group = get_object_or_404(AccessGroup, pk=group_id)
            # Проверяем, что группа ещё не добавлена
            if not GroupContainerGroup.objects.filter(group_container=container, access_group=group).exists():
                GroupContainerGroup.objects.create(group_container=container, access_group=group, added_by=request.user)
                messages.success(request, 'Группа добавлена в контейнер.')
            else:
                messages.warning(request, 'Группа уже добавлена в контейнер.')
        
        return redirect('access:container_detail', pk=container.pk)


class GroupContainerGroupDeleteView(LoginRequiredMixin, View):
    """Удаление группы из контейнера."""

    def post(self, request, *args, **kwargs):
        container = get_object_or_404(GroupContainer, pk=kwargs['container_pk'])
        group_id = request.POST.get('group_id')
        
        if group_id:
            GroupContainerGroup.objects.filter(group_container=container, access_group_id=group_id).delete()
            messages.success(request, 'Группа удалена из контейнера.')
        
        return redirect('access:container_detail', pk=container.pk)


# ============================================================================
# Привязка ролей к должностям
# ============================================================================

class PositionRoleListView(LoginRequiredMixin, ListView):
    """Список должностей с привязанными ролями."""
    model = Position
    template_name = 'access/position_roles.html'
    context_object_name = 'positions'
    paginate_by = 50

    def get_queryset(self):
        qs = Position.objects.filter(is_active=True).select_related('department')
        
        # Фильтр по подразделению
        dept_id = self.request.GET.get('dept')
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        
        # Фильтр по должности
        position_name = self.request.GET.get('position')
        if position_name:
            qs = qs.filter(name__icontains=position_name)
        
        # Сортировка по столбцам
        order_by = self.request.GET.get('order_by', 'department')
        valid_orders = {
            'department': 'department__name',
            'position': 'name',
            'roles': 'name',
        }
        qs = qs.order_by(valid_orders.get(order_by, 'department__name'))
        
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = Role.objects.filter(is_active=True).order_by('name')
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['positions_count'] = Position.objects.filter(is_active=True).count()
        # Передаём текущие значения фильтров для отображения в шаблоне
        context['current_dept'] = self.request.GET.get('dept', '')
        context['current_position'] = self.request.GET.get('position', '')
        return context


class PositionRoleAddView(LoginRequiredMixin, View):
    """Добавление роли к должности."""

    def post(self, request, *args, **kwargs):
        position = get_object_or_404(Position, pk=kwargs['pk'])
        role_id = request.POST.get('role')

        if role_id:
            role = get_object_or_404(Role, pk=role_id)
            if not PositionRole.objects.filter(position=position, role=role).exists():
                PositionRole.objects.create(position=position, role=role, added_by=request.user)
                messages.success(request, f'Роль "{role.name}" добавлена к должности "{position.name}".')
            else:
                messages.warning(request, 'Эта роль уже привязана к должности.')

        return redirect('access:position_roles')


class PositionRoleDeleteView(LoginRequiredMixin, View):
    """Удаление привязки роли к должности."""

    def post(self, request, *args, **kwargs):
        position_role = get_object_or_404(
            PositionRole,
            pk=kwargs['pk'],
            position__is_active=True,
        )
        position_name = position_role.position.name
        role_name = position_role.role.name
        position_role.delete()
        messages.success(request, f'Роль "{role_name}" отвязана от должности "{position_name}".')
        return redirect('access:position_roles')


class PositionRoleExportCsvView(LoginRequiredMixin, View):
    """Выгрузка привязки ролей к должностям в CSV."""

    def get(self, request, *args, **kwargs):
        import csv
        import io
        from django.http import HttpResponse

        qs = Position.objects.filter(is_active=True).select_related('department')

        # Фильтр по подразделению
        dept_id = request.GET.get('dept')
        if dept_id:
            qs = qs.filter(department_id=dept_id)

        # Фильтр по должности
        position_name = request.GET.get('position')
        if position_name:
            qs = qs.filter(name__icontains=position_name)

        # Сортировка
        order_by = request.GET.get('order_by', 'department')
        valid_orders = {
            'department': 'department__name',
            'position': 'name',
            'roles': 'name',
        }
        qs = qs.order_by(valid_orders.get(order_by, 'department__name'))

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow([
            'Подразделение',
            'Должность',
            'Код 1С',
            'Привязанные роли',
            'Гранты текущие',
            'Гранты по ролям',
        ])

        for position in qs:
            # Привязанные роли
            roles = position.position_roles.select_related('role').all()
            role_names = [pr.role.name for pr in roles]

            # Собираем все AccessGroup, связанные с ролями должности
            group_ids_by_role = {}  # role_id -> list of group_ids
            all_group_ids = set()

            for pr in roles:
                role_group_ids = list(
                    RoleGroup.objects.filter(role=pr.role)
                    .values_list('access_group_id', flat=True)
                )
                group_ids_by_role[pr.role.pk] = role_group_ids
                all_group_ids.update(role_group_ids)

            # Текущие гранты для всех групп должности
            current_grants = AccessGrant.objects.filter(
                group_id__in=all_group_ids,
                is_active=True,
                revoked_at__isnull=True,
            ).select_related('user', 'external_user', 'group').distinct()

            grants_current = []
            for g in current_grants:
                if g.external_user:
                    who = g.external_user.full_name
                elif g.user:
                    who = g.user.get_full_name()
                else:
                    who = '?'
                grants_current.append(f'{who} → {g.group.name}')

            # Гранты по каждой роли
            grants_by_role = []
            for pr in roles:
                role_group_ids = group_ids_by_role.get(pr.role.pk, [])
                if not role_group_ids:
                    grants_by_role.append(f'{pr.role.name}: —')
                    continue

                role_grants = AccessGrant.objects.filter(
                    group_id__in=role_group_ids,
                    is_active=True,
                    revoked_at__isnull=True,
                ).select_related('user', 'external_user', 'group').distinct()

                if role_grants:
                    grant_list = []
                    for g in role_grants:
                        if g.external_user:
                            who = g.external_user.full_name
                        elif g.user:
                            who = g.user.get_full_name()
                        else:
                            who = '?'
                        grant_list.append(f'{who} → {g.group.name}')
                    grants_by_role.append(f'{pr.role.name}: {"; ".join(grant_list)}')
                else:
                    grants_by_role.append(f'{pr.role.name}: —')

            writer.writerow([
                position.department.name if position.department else '—',
                position.name,
                position.code_1c or '—',
                '; '.join(role_names) if role_names else '—',
                '; '.join(grants_current) if grants_current else '—',
                '; '.join(grants_by_role) if grants_by_role else '—',
            ])

        csv_bytes = output.getvalue().encode('utf-8-sig')
        response = HttpResponse(csv_bytes, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=position_roles.csv'
        return response


# ============================================================================
# Аудит доступа
# ============================================================================

class AccessAuditView(LoginRequiredMixin, View):
    """Аудит доступа: проверка грантов по CSV файлу."""

    template_name = 'access/access_audit.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            'missing_grants': [],
            'not_found_users': [],
        })

    def post(self, request, *args, **kwargs):
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'Выберите CSV файл.')
            return render(request, self.template_name, {
                'missing_grants': [],
                'not_found_users': [],
            })

        import csv
        from io import TextIOWrapper

        missing_grants = []
        not_found_users = []
        external_missing_grants = []

        try:
            stream = TextIOWrapper(csv_file, encoding='utf-8-sig')
            reader = csv.reader(stream)
            rows = list(reader)
        except Exception as e:
            messages.error(request, f'Ошибка чтения CSV файла: {e}')
            return render(request, self.template_name, {
                'missing_grants': [],
                'not_found_users': [],
            })

        if not rows:
            messages.warning(request, 'CSV файл пуст.')
            return render(request, self.template_name, {
                'missing_grants': [],
                'not_found_users': [],
            })

        # Пропускаем заголовок
        data_rows = rows[1:]

        for row in data_rows:
            if not row or all(not cell.strip() for cell in row):
                continue

            # Первый столбец — DisplayName (ФИО)
            display_name = row[0].strip() if len(row) > 0 else ''
            # Второй столбец — SamAccountName (логин)
            sam_account_name = row[1].strip() if len(row) > 1 else ''
            # Последний столбец — SecurityGroups
            groups_str = row[-1].strip() if len(row) > 1 else ''
            # Email (третий столбец)
            email = row[2].strip() if len(row) > 2 else ''

            if not display_name:
                continue

            # Ищем пользователя во внутренней базе
            user = self._find_user(display_name)
            
            # Если не найден, ищем во внешних сотрудниках
            external_user = None
            if not user:
                external_user = self._find_external_user(display_name)

            if not user and not external_user:
                not_found_users.append({
                    'display_name': display_name,
                    'sam_account_name': sam_account_name or '—',
                    'email': email or '—',
                    'groups': groups_str or '—',
                })
                continue

            # Парсим группы
            if groups_str:
                group_names = [g.strip() for g in groups_str.split(':') if g.strip()]
            else:
                group_names = []

            # Проверяем каждый грант
            for group_name in group_names:
                access_group = AccessGroup.objects.filter(
                    models.Q(name__iexact=group_name) | models.Q(old_name__iexact=group_name)
                ).first()

                if not access_group:
                    continue

                # Проверяем гранты для внутреннего пользователя
                if user:
                    has_active_grant = AccessGrant.objects.filter(
                        user=user,
                        group=access_group,
                        is_active=True,
                    ).exists()

                    if not has_active_grant:
                        missing_grants.append({
                            'user': user.get_full_name(),
                            'sam_account_name': sam_account_name or '—',
                            'username': user.username,
                            'email': user.corporate_email or '—',
                            'is_fired': user.is_fired,
                            'group': access_group.name,
                            'source': 'Сотрудник',
                        })
                
                # Проверяем гранты для внешнего сотрудника
                if external_user:
                    has_active_grant = AccessGrant.objects.filter(
                        external_user=external_user,
                        group=access_group,
                        grant_type='external',
                        is_active=True,
                    ).exists()

                    if not has_active_grant:
                        external_missing_grants.append({
                            'user': external_user.full_name,
                            'sam_account_name': sam_account_name or '—',
                            'email': email or '—',
                            'department': external_user.department or '—',
                            'position': external_user.position or '—',
                            'group': access_group.name,
                            'source': 'Внешний сотрудник',
                        })

        # Сохраняем не найденных в сессии для выгрузки
        self.request.session['audit_not_found_users'] = not_found_users

        return render(request, self.template_name, {
            'missing_grants': missing_grants,
            'not_found_users': not_found_users,
            'external_missing_grants': external_missing_grants,
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Восстанавливаем не найденных из сессии для выгрузки
        context['not_found_users'] = self.request.session.get('audit_not_found_users', [])
        return context

    def _find_user(self, display_name):
        """Ищет пользователя по полному имени (ФИО)."""
        display_name = display_name.strip()
        if not display_name:
            return None

        # Если DisplayName похож на логин
        if len(display_name) < 50 and ' ' not in display_name:
            return User.objects.filter(
                models.Q(username__iexact=display_name) |
                models.Q(corporate_email__iexact=display_name)
            ).first()

        parts = display_name.split()
        if len(parts) < 2:
            return User.objects.filter(
                models.Q(username__iexact=display_name) |
                models.Q(corporate_email__iexact=display_name)
            ).first()

        last_name = parts[0]
        first_name = parts[1]
        patronymic = ' '.join(parts[2:]) if len(parts) > 2 else ''

        qs = User.objects.filter(
            last_name__iexact=last_name,
            first_name__iexact=first_name,
        )

        if patronymic:
            user = qs.filter(patronymic__iexact=patronymic).first()
            if user:
                return user
            user = qs.filter(patronymic__icontains=patronymic).first()
            if user:
                return user

        return qs.first()

    def _find_external_user(self, display_name):
        """Ищет внешнего сотрудника по полному имени (ФИО)."""
        display_name = display_name.strip()
        if not display_name:
            return None

        # Если DisplayName похож на логин
        if len(display_name) < 50 and ' ' not in display_name:
            return ExternalUser.objects.filter(
                models.Q(full_name__icontains=display_name)
            ).first()

        parts = display_name.split()
        if len(parts) < 2:
            return ExternalUser.objects.filter(
                models.Q(full_name__icontains=display_name)
            ).first()

        last_name = parts[0]
        first_name = parts[1]
        patronymic = ' '.join(parts[2:]) if len(parts) > 2 else ''

        qs = ExternalUser.objects.filter(
            models.Q(full_name__icontains=last_name),
        )

        if patronymic:
            user = qs.filter(full_name__icontains=f'{first_name} {patronymic}').first()
            if user:
                return user
            user = qs.filter(full_name__icontains=first_name).first()
            if user:
                return user

        return qs.first()


class AccessAuditExportView(LoginRequiredMixin, View):
    """Выгрузка аудита в Excel."""

    def get(self, request, *args, **kwargs):
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
        except ImportError:
            messages.error(request, 'Модуль openpyxl не установлен.')
            return redirect('access:audit')

        # Получаем данные для аудита
        missing_grants = []
        external_missing_grants = []
        not_found_users = []

        # Читаем последний загруженный файл из сессии или используем текущий
        # Для простоты — делаем запрос без файла, показываем текущие данные
        users = User.objects.filter(is_active=True)

        for user in users:
            groups_str = request.GET.get('groups', '')
            if groups_str:
                group_names = [g.strip() for g in groups_str.split(':') if g.strip()]
            else:
                continue

            for group_name in group_names:
                access_group = AccessGroup.objects.filter(
                    models.Q(name__iexact=group_name) | models.Q(old_name__iexact=group_name)
                ).first()
                if not access_group:
                    continue

                has_active_grant = AccessGrant.objects.filter(
                    user=user,
                    group=access_group,
                    is_active=True,
                ).exists()

                if not has_active_grant:
                    missing_grants.append({
                        'user': user.get_full_name(),
                        'username': user.username,
                        'email': user.corporate_email or '—',
                        'is_fired': user.is_fired,
                        'group': access_group.name,
                        'source': 'Сотрудник',
                    })

        # Проверяем внешних сотрудников
        external_users = ExternalUser.objects.filter(is_active=True).select_related('contract', 'contract__organization')

        for external_user in external_users:
            groups_str = request.GET.get('groups', '')
            if groups_str:
                group_names = [g.strip() for g in groups_str.split(':') if g.strip()]
            else:
                continue

            for group_name in group_names:
                access_group = AccessGroup.objects.filter(
                    models.Q(name__iexact=group_name) | models.Q(old_name__iexact=group_name)
                ).first()
                if not access_group:
                    continue

                has_active_grant = AccessGrant.objects.filter(
                    external_user=external_user,
                    group=access_group,
                    grant_type='external',
                    is_active=True,
                ).exists()

                if not has_active_grant:
                    external_missing_grants.append({
                        'user': external_user.full_name,
                        'email': '',
                        'department': external_user.department or '—',
                        'position': external_user.position or '—',
                        'group': access_group.name,
                        'source': 'Внешний сотрудник',
                    })

        # Создаём Excel файл
        wb = Workbook()
        ws = wb.active
        ws.title = 'Аудит доступа'

        # Объединяем списки
        all_missing = missing_grants + external_missing_grants

        # Заголовки
        headers = ['Источник', 'ФИО', 'Логин/Email', 'Подразделение', 'Должность', 'Группа доступа']
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')

        # Данные
        for row_idx, item in enumerate(all_missing, 2):
            ws.cell(row=row_idx, column=1, value=item['source'])
            ws.cell(row=row_idx, column=2, value=item['user'])
            ws.cell(row=row_idx, column=3, value=item.get('username', item.get('email', '—')))
            ws.cell(row=row_idx, column=4, value=item.get('department', '—'))
            ws.cell(row=row_idx, column=5, value=item.get('position', '—'))
            ws.cell(row=row_idx, column=6, value=item['group'])

        # Автоширина колонок
        for col in ws.columns:
            max_length = 0
            column_letter = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            ws.column_dimensions[column_letter].width = max_length + 10

        # Ответ
        from django.http import HttpResponse
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=access_audit.xlsx'
        wb.save(response)
        return response


class AccessAuditNotFoundExportView(LoginRequiredMixin, View):
    """Выгрузка ненайденных пользователей в CSV."""

    def get(self, request, *args, **kwargs):
        import csv
        import io
        from django.http import HttpResponse

        # Получаем данные из сессии или генерируем заново
        not_found_users = request.session.get('audit_not_found_users', [])

        if not not_found_users:
            messages.warning(request, 'Нет данных для выгрузки. Сначала выполните проверку.')
            return redirect('access:audit')

        # Создаём CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Заголовок
        writer.writerow(['DisplayName', 'SamAccountName', 'Email', 'Группы'])
        
        # Данные
        for item in not_found_users:
            writer.writerow([
                item['display_name'],
                item['sam_account_name'],
                item['email'],
                item['groups'],
            ])

        # Ответ
        csv_bytes = output.getvalue().encode('utf-8-sig')
        response = HttpResponse(
            csv_bytes,
            content_type='text/csv; charset=utf-8'
        )
        response['Content-Disposition'] = 'attachment; filename=not_found_users.csv'
        return response


# ============================================================================
# Подрядчики — CRUD
# ============================================================================

class OrganizationListView(LoginRequiredMixin, ListView):
    """Список организаций-подрядчиков."""
    model = Organization
    template_name = 'access/organization_list.html'
    context_object_name = 'organizations'
    paginate_by = 50

    def get_queryset(self):
        qs = Organization.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                models.Q(name__icontains=q) | models.Q(inn__icontains=q)
            )
        return qs.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizations_count'] = Organization.objects.count()
        context['current_q'] = self.request.GET.get('q', '')
        return context


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    """Создание организации-подрядчика."""
    model = Organization
    form_class = OrganizationForm
    template_name = 'access/organization_form.html'
    success_url = reverse_lazy('access:organization_list')

    def form_valid(self, form):
        messages.success(self.request, 'Организация успешно создана.')
        return super().form_valid(form)


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    """Детали организации-подрядчика."""
    model = Organization
    template_name = 'access/organization_detail.html'
    context_object_name = 'organization'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contracts'] = self.object.contracts.all()
        return context


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование организации-подрядчика."""
    model = Organization
    form_class = OrganizationForm
    template_name = 'access/organization_form.html'
    success_url = reverse_lazy('access:organization_list')

    def form_valid(self, form):
        messages.success(self.request, 'Организация успешно обновлена.')
        return super().form_valid(form)


class OrganizationDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление организации-подрядчика."""
    model = Organization
    success_url = reverse_lazy('access:organization_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Организация успешно удалена.')
        return super().delete(request, *args, **kwargs)


class ContractListView(LoginRequiredMixin, ListView):
    """Список договоров."""
    model = Contract
    template_name = 'access/contract_list.html'
    context_object_name = 'contracts'
    paginate_by = 50

    def get_queryset(self):
        qs = Contract.objects.select_related('organization')
        q = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '')
        
        if q:
            qs = qs.filter(
                models.Q(number__icontains=q) | models.Q(organization__name__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        
        return qs.order_by('-date_to')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contracts_count'] = Contract.objects.count()
        context['current_q'] = self.request.GET.get('q', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['status_choices'] = Contract.Status.choices
        return context


class ContractCreateView(LoginRequiredMixin, CreateView):
    """Создание договора."""
    model = Contract
    form_class = ContractForm
    template_name = 'access/contract_form.html'
    success_url = reverse_lazy('access:contract_list')

    def form_valid(self, form):
        messages.success(self.request, 'Договор успешно создан.')
        return super().form_valid(form)


class ContractDetailView(LoginRequiredMixin, DetailView):
    """Детали договора."""
    model = Contract
    template_name = 'access/contract_detail.html'
    context_object_name = 'contract'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['external_users'] = self.object.external_users.all()
        return context


class ContractUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование договора."""
    model = Contract
    form_class = ContractForm
    template_name = 'access/contract_form.html'
    success_url = reverse_lazy('access:contract_list')

    def form_valid(self, form):
        messages.success(self.request, 'Договор успешно обновлён.')
        return super().form_valid(form)


class ContractDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление договора."""
    model = Contract
    success_url = reverse_lazy('access:contract_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Договор успешно удалён.')
        return super().delete(request, *args, **kwargs)


class ExternalUserListView(LoginRequiredMixin, ListView):
    """Список внешних лиц."""
    model = ExternalUser
    template_name = 'access/external_user_list.html'
    context_object_name = 'external_users'
    paginate_by = 50

    def get_queryset(self):
        qs = ExternalUser.objects.select_related('contract', 'contract__organization')
        q = self.request.GET.get('q', '').strip()
        contract_id = self.request.GET.get('contract', '')
        
        if q:
            qs = qs.filter(
                models.Q(full_name__icontains=q) | models.Q(position__icontains=q)
            )
        if contract_id:
            qs = qs.filter(contract_id=contract_id)
        
        return qs.order_by('full_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['external_users_count'] = ExternalUser.objects.count()
        context['current_q'] = self.request.GET.get('q', '')
        context['current_contract'] = self.request.GET.get('contract', '')
        context['contracts'] = Contract.objects.all().order_by('-date_to')
        return context


class ExternalUserCreateView(LoginRequiredMixin, CreateView):
    """Создание внешнего лица."""
    model = ExternalUser
    form_class = ExternalUserForm
    template_name = 'access/external_user_form.html'
    success_url = reverse_lazy('access:external_user_list')

    def form_valid(self, form):
        messages.success(self.request, 'Внешнее лицо успешно создано.')
        return super().form_valid(form)


class ExternalUserDetailView(LoginRequiredMixin, DetailView):
    """Детали внешнего лица."""
    model = ExternalUser
    template_name = 'access/external_user_detail.html'
    context_object_name = 'external_user'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class ExternalUserUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование внешнего лица."""
    model = ExternalUser
    form_class = ExternalUserForm
    template_name = 'access/external_user_form.html'
    success_url = reverse_lazy('access:external_user_list')

    def form_valid(self, form):
        messages.success(self.request, 'Внешнее лицо успешно обновлено.')
        return super().form_valid(form)


class ExternalUserDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление внешнего лица."""
    model = ExternalUser
    success_url = reverse_lazy('access:external_user_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Внешнее лицо успешно удалено.')
        return super().delete(request, *args, **kwargs)


class ExternalUserImportView(LoginRequiredMixin, View):
    """Импорт внешних лиц из CSV файла."""

    template_name = 'access/external_user_import.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            'success_results': [],
            'error_results': [],
            'statistics': {},
        })

    def post(self, request, *args, **kwargs):
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'Выберите CSV файл.')
            return render(request, self.template_name, {
                'success_results': [],
                'error_results': [],
                'statistics': {},
            })

        import csv
        import io
        from django.db import transaction

        success_results = []
        error_results = []
        statistics = {
            'total_rows': 0,
            'created': 0,
            'updated': 0,
            'skipped_duplicates': 0,
            'skipped_empty': 0,
            'errors': 0,
        }

        try:
            # Read file with proper encoding
            file_content = csv_file.read().decode('utf-8-sig')
            reader = csv.reader(io.StringIO(file_content))
            
            # Skip header
            header = next(reader, None)
            if not header:
                messages.error(request, 'CSV файл пуст или не содержит заголовка.')
                return render(request, self.template_name, {
                    'success_results': [],
                    'error_results': [],
                    'statistics': {},
                })

            # Find organization by INN (default to first organization if not specified)
            org = Organization.objects.first()
            if not org:
                messages.error(request, 'Организации не найдены. Сначала создайте организацию.')
                return render(request, self.template_name, {
                    'success_results': [],
                    'error_results': [],
                    'statistics': {},
                })

            # Find the most recent active contract for this organization
            contracts = Contract.objects.filter(organization=org).order_by('-date_to')
            contract = None
            for c in contracts:
                if c.status == Contract.Status.ACTIVE:
                    contract = c
                    break
            if not contract:
                for c in contracts:
                    if c.status not in [Contract.Status.CLOSED, Contract.Status.TERMINATED]:
                        contract = c
                        break
            if not contract:
                messages.error(request, 'Подходящий договор не найден.')
                return render(request, self.template_name, {
                    'success_results': [],
                    'error_results': [],
                    'statistics': {},
                })

            current_department = ""
            row_number = 1

            with transaction.atomic():
                for row in reader:
                    row_number += 1
                    statistics['total_rows'] += 1

                    # Pad row to 4 columns if needed
                    while len(row) < 4:
                        row.append('')

                    fio_raw = row[0].strip()
                    position_raw = row[1].strip()
                    email_raw = row[2].strip()
                    phone_raw = row[3].strip()

                    # Skip empty rows
                    if not fio_raw:
                        statistics['skipped_empty'] += 1
                        continue

                    # Check if this is a department header
                    if not position_raw and not email_raw and not phone_raw:
                        current_department = fio_raw
                        continue

                    # This is an employee row
                    # Extract only first 3 words from ФИО
                    fio_words = fio_raw.split()
                    if len(fio_words) >= 3:
                        full_name = ' '.join(fio_words[:3])
                    else:
                        full_name = fio_raw

                    # Clean up position
                    if position_raw in ['-', ',-', '']:
                        position_raw = ''

                    # Build department-based position
                    if current_department and position_raw:
                        final_position = f"{current_department}-{position_raw}"
                    elif position_raw:
                        final_position = position_raw
                    else:
                        final_position = ''

                    # Clean email - take first email if multiple
                    email = ''
                    if email_raw:
                        emails = [e.strip() for e in email_raw.split('\n') if '@' in e]
                        if emails:
                            email = emails[0]

                    # Clean phone
                    phone = ''
                    if phone_raw:
                        phone = ''.join(ch for ch in phone_raw if ch.isdigit() or ch in '()-+ ')
                        phone = phone.strip()

                    # Skip if no position and no department
                    if not final_position and not current_department:
                        statistics['skipped_empty'] += 1
                        continue

                    try:
                        obj, is_new = ExternalUser.objects.update_or_create(
                            contract=contract,
                            full_name=full_name,
                            defaults={
                                'user_type': ExternalUser.UserType.CONTRACTOR_EMPLOYEE,
                                'department': current_department,
                                'position': final_position,
                                'id_doc_no': phone,
                                'is_active': True,
                            }
                        )
                        
                        if is_new:
                            statistics['created'] += 1
                            success_results.append({
                                'row': row_number,
                                'name': full_name,
                                'department': current_department,
                                'position': final_position,
                                'email': email,
                                'phone': phone,
                                'action': 'Создан',
                            })
                        else:
                            statistics['updated'] += 1
                            statistics['skipped_duplicates'] += 1
                            success_results.append({
                                'row': row_number,
                                'name': full_name,
                                'department': current_department,
                                'position': final_position,
                                'email': email,
                                'phone': phone,
                                'action': 'Обновлён',
                            })
                    except Exception as e:
                        statistics['errors'] += 1
                        error_results.append({
                            'row': row_number,
                            'name': full_name,
                            'department': current_department,
                            'position': final_position,
                            'error': str(e),
                        })

        except Exception as e:
            messages.error(request, f'Ошибка при обработке файла: {e}')
            return render(request, self.template_name, {
                'success_results': [],
                'error_results': [],
                'statistics': {},
            })

        # Add summary to statistics
        statistics['summary'] = (
            f'Всего строк: {statistics["total_rows"]} | '
            f'Создано: {statistics["created"]} | '
            f'Обновлено: {statistics["updated"]} | '
            f'Пропущено (пустые): {statistics["skipped_empty"]} | '
            f'Ошибки: {statistics["errors"]}'
        )

        messages.success(request, f'Импорт завершён. {statistics["summary"]}')
        return render(request, self.template_name, {
            'success_results': success_results,
            'error_results': error_results,
            'statistics': statistics,
        })
