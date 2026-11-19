import json
import logging
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.text import slugify
import openpyxl

from accounts.models import User, Department
from .models import TrainingType, Training, TrainingEnrollment, TrainingCategory, TrainingGoal, SkillspaceGroup
from .forms import TrainingTypeForm, TrainingForm, TrainingUserSelectionForm, TrainingCategoryForm, TrainingGoalForm
from .services.skillspace_api import (
    SkillspaceClient, SkillspaceAPIError,
    invite_student_to_training, sync_training_to_skillspace,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Training Categories
# ============================================================================

@login_required
def training_category_list(request):
    """Список категорий обучения."""
    query = request.GET.get('q', '').strip()
    
    categories = TrainingCategory.objects.all()
    if query:
        categories = categories.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )
    
    categories = categories.order_by('name')
    
    return render(request, 'training/category_list.html', {
        'categories': categories,
        'query': query,
    })


@login_required
def training_category_create(request):
    """Создание категории обучения."""
    if request.method == 'POST':
        form = TrainingCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Категория создана')
            return redirect('training:category_list')
    else:
        form = TrainingCategoryForm()
    
    return render(request, 'training/category_form.html', {
        'form': form,
        'action': 'Создание',
    })


@login_required
def training_category_edit(request, pk):
    """Редактирование категории обучения."""
    category = get_object_or_404(TrainingCategory, pk=pk)
    
    if request.method == 'POST':
        form = TrainingCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Категория обновлена')
            return redirect('training:category_list')
    else:
        form = TrainingCategoryForm(instance=category)
    
    return render(request, 'training/category_form.html', {
        'form': form,
        'category': category,
        'action': 'Редактирование',
    })


@login_required
def training_category_delete(request, pk):
    """Удаление категории обучения."""
    category = get_object_or_404(TrainingCategory, pk=pk)
    
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Категория удалена')
        return redirect('training:category_list')
    
    return render(request, 'training/category_confirm_delete.html', {
        'obj': category,
    })


# ============================================================================
# Training Types
# ============================================================================

@login_required
def training_type_list(request):
    """Список типов обучения."""
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    
    types = TrainingType.objects.all()
    
    # Filter by category
    if category_id:
        types = types.filter(category_id=category_id)
    
    if query:
        types = types.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )
    
    types = types.order_by('-created_at')
    
    # Count active for stats
    active_types = TrainingType.objects.filter(is_active=True)
    if category_id:
        active_types = active_types.filter(category_id=category_id)
    if query:
        active_types = active_types.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )
    
    # Get all categories for filter
    categories = TrainingCategory.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'training/type_list.html', {
        'types': types,
        'active_types_count': active_types.count(),
        'categories': categories,
        'query': query,
        'selected_category': category_id,
    })


@login_required
def training_course_list(request):
    """Справочник курсов Skillspace."""
    # Fetch courses from Skillspace API
    courses = []
    last_updated = None
    try:
        client = SkillspaceClient()
        courses = client.get_course_list()
        last_updated = timezone.now().strftime('%d.%m.%Y %H:%M:%S')
    except SkillspaceAPIError as e:
        messages.error(request, f'Ошибка загрузки курсов: {e}')
        logger.error(f'Failed to fetch course list: {e}')

    # Build a map of skillspace_course_id -> TrainingType pk for active check
    training_types = TrainingType.objects.filter(is_active=True)
    course_active_map = {}
    for tt in training_types:
        if tt.skillspace_course_id is not None:
            course_active_map[tt.skillspace_course_id] = tt.pk

    return render(request, 'training/course_list.html', {
        'courses': courses,
        'last_updated': last_updated,
        'course_active_map': course_active_map,
    })


@login_required
def training_course_toggle(request, course_id):
    """Переключение видимости курса (is_active TrainingType)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    course_id_str = str(course_id).strip()

    training_type = TrainingType.objects.filter(
        skillspace_course_id=course_id_str
    ).first()

    if not training_type:
        return JsonResponse({
            'error': 'Training type not found',
            'created': True,
        })

    training_type.is_active = not training_type.is_active
    training_type.save(update_fields=['is_active'])

    return JsonResponse({
        'status': 'ok',
        'is_active': training_type.is_active,
        'training_type_id': training_type.pk,
    })


@login_required
def training_type_create(request):
    """Создание типа обучения."""
    course_uuid = request.GET.get('course_uuid', '')
    
    if request.method == 'POST':
        form = TrainingTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Обучающий курс создан')
            return redirect('training:type_list')
    else:
        form = TrainingTypeForm()
        if course_uuid:
            form.fields['skillspace_course'].initial = course_uuid
    
    return render(request, 'training/training_type_form.html', {
        'form': form,
        'action': 'Создание',
    })


@login_required
def training_type_edit(request, pk):
    """Редактирование обучающего курса."""
    training_type = get_object_or_404(TrainingType, pk=pk)
    
    if request.method == 'POST':
        form = TrainingTypeForm(request.POST, instance=training_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Обучающий курс обновлён')
            return redirect('training:type_list')
    else:
        form = TrainingTypeForm(instance=training_type)
    
    return render(request, 'training/training_type_form.html', {
        'form': form,
        'training_type': training_type,
        'action': 'Редактирование',
    })


@login_required
def training_type_delete(request, pk):
    """Удаление типа обучения."""
    training_type = get_object_or_404(TrainingType, pk=pk)
    
    if request.method == 'POST':
        training_type.is_active = False
        training_type.save()
        messages.success(request, 'Обучающий курс удалён')
        return redirect('training:type_list')
    
    return render(request, 'training/training_type_confirm_delete.html', {
        'obj': training_type,
    })


@login_required
def training_detail(request, pk):
    """Детали назначения обучения."""
    training = get_object_or_404(
        Training.objects.select_related('training_type')
        .prefetch_related('enrollments__user', 'enrollments__user__department'),
        pk=pk,
    )

    # Filter enrollments by status
    status_filter = request.GET.get('status')
    if status_filter:
        enrollments = training.enrollments.filter(status=status_filter)
    else:
        enrollments = training.enrollments.all()

    enrollments = enrollments.select_related('user', 'user__department').order_by('user__last_name')

    # Calculate stats
    total = training.enrollments.count()
    not_started = training.enrollments.filter(status='not_started').count()
    in_progress = training.enrollments.filter(status='in_progress').count()
    completed = training.enrollments.filter(status='completed').count()
    failed = training.enrollments.filter(status='failed').count()

    context = {
        'training': training,
        'enrollments': enrollments,
        'status_filter': status_filter,
        'status_choices': TrainingEnrollment.Status.choices,
        'stats': {
            'total': total,
            'not_started': not_started,
            'in_progress': in_progress,
            'completed': completed,
            'failed': failed,
        },
    }
    return render(request, 'training/training_detail.html', context)


@login_required
def training_edit(request, pk):
    """Редактирование назначения обучения."""
    training = get_object_or_404(Training, pk=pk)

    # Sync groups from API before showing form
    if training.training_type.skillspace_course_id:
        SkillspaceGroup.sync_from_api(training.training_type.skillspace_course_id)

    if request.method == 'POST':
        form = TrainingForm(request.POST, instance=training)
        if form.is_valid():
            form.save()
            messages.success(request, 'Обучение обновлено')
            return redirect('training:training_detail', pk=training.pk)
        else:
            # Debug: log form errors
            logger.error(f'Form validation errors: {form.errors}')
    else:
        form = TrainingForm(instance=training)

    return render(request, 'training/training_form.html', {
        'form': form,
        'training': training,
        'training_type': training.training_type,
        'action': 'Редактирование',
    })


@login_required
def training_delete(request, pk):
    """Удаление назначения обучения."""
    training = get_object_or_404(Training, pk=pk)
    if request.method == 'POST':
        training.is_active = False
        training.status = Training.Status.ARCHIVED
        training.save()
        messages.success(request, 'Обучение архивировано')
        return redirect('training:type_trainings', type_pk=training.training_type.pk)

    return render(request, 'training/training_confirm_delete.html', {'obj': training})


@login_required
def training_sync(request, pk):
    """Синхронизация обучения с Skillspace — массовая запись студентов."""
    training = get_object_or_404(Training, pk=pk)

    try:
        result = sync_training_to_skillspace(training)
        
        if 'error' in result:
            messages.error(request, f'Ошибка синхронизации: {result["error"]}')
        else:
            added_count = len(result.get('added', []))
            already_count = len(result.get('already_enrolled', []))
            error_count = len(result.get('errors', []))
            
            msg = f'Синхронизация завершена'
            if added_count:
                msg += f': добавлено {added_count}'
            if already_count:
                msg += f', уже записано {already_count}'
            if error_count:
                msg += f', ошибок {error_count}'
            
            messages.success(request, msg)
            
            if error_count:
                for err in result.get('errors', []):
                    messages.warning(request, f'{err["user"]}: {err["error"]}')
            
            # Store sync result in session for display on detail page
            request.session[f'sync_result_{pk}'] = {
                'added': result.get('added', []),
                'already_enrolled': result.get('already_enrolled', []),
                'errors': result.get('errors', []),
                'synced_at': timezone.now().strftime('%d.%m.%Y %H:%M'),
            }
                    
    except Exception as e:
        logger.error(f'Sync error for training {pk}: {e}')
        messages.error(request, f'Ошибка синхронизации: {str(e)}')

    return redirect('training:training_detail', pk=pk)


@login_required
def training_sync_status(request, pk):
    """AJAX: Получить детальный статус синхронизации обучения."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    training = get_object_or_404(Training, pk=pk)
    
    # Get sync result from session (just performed)
    session_key = f'sync_result_{pk}'
    recent_result = request.session.pop(session_key, None)
    
    # Get enrollment breakdown
    total = training.enrollments.count()
    not_started = training.enrollments.filter(status='not_started').count()
    in_progress = training.enrollments.filter(status='in_progress').count()
    completed = training.enrollments.filter(status='completed').count()
    failed = training.enrollments.filter(status='failed').count()
    
    # Count added/enrolled from recent sync
    added = recent_result.get('added', []) if recent_result else []
    already_enrolled = recent_result.get('already_enrolled', []) if recent_result else []
    errors = recent_result.get('errors', []) if recent_result else []
    
    return JsonResponse({
        'status': 'ok',
        'total': total,
        'not_started': not_started,
        'in_progress': in_progress,
        'completed': completed,
        'failed': failed,
        'last_sync_at': training.last_sync_at.strftime('%d.%m.%Y %H:%M') if training.last_sync_at else None,
        'recent_sync': {
            'added': added,
            'already_enrolled': already_enrolled,
            'errors': errors,
            'synced_at': recent_result.get('synced_at') if recent_result else None,
        } if recent_result else None,
    })


@login_required
def search_users(request):
    """AJAX: Поиск сотрудников по ФИО и табельному номеру."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET allowed'}, status=405)
    
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'users': []})
    
    # Search by full name or tab_number
    users = User.objects.filter(
        Q(last_name__icontains=query) |
        Q(first_name__icontains=query) |
        Q(patronymic__icontains=query) |
        Q(tab_number__icontains=query) |
        Q(employee_code_1c__icontains=query)
    ).exclude(
        is_fired=True
    ).select_related('department').order_by('last_name', 'first_name')[:20]
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'full_name': user.get_full_name(),
            'last_name': user.last_name,
            'first_name': user.first_name,
            'patronymic': user.patronymic,
            'tab_number': user.tab_number or '—',
            'employee_code': user.employee_code_1c or '—',
            'department': user.department.name if user.department else '—',
            'email': user.corporate_email or user.personal_email or '—',
        })
    
    return JsonResponse({'users': users_data})


@login_required
def search_departments(request):
    """AJAX: Поиск подразделений по названию или получение пользователей по ID отделов."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET allowed'}, status=405)
    
    try:
        # Если переданы dept_ids — возвращаем пользователей для превью
        dept_ids = request.GET.getlist('dept_ids[]') or request.GET.getlist('dept_ids')
        if dept_ids:
            try:
                dept_ids = [int(d) for d in dept_ids]
            except (ValueError, TypeError):
                return JsonResponse({'users': []})
            
            users = User.objects.filter(
                department_id__in=dept_ids,
                is_active=True,
                is_fired=False,
            ).select_related('department').order_by('last_name', 'first_name')[:100]
            
            users_data = []
            for user in users:
                users_data.append({
                    'id': user.id,
                    'full_name': user.get_full_name(),
                    'last_name': user.last_name,
                    'first_name': user.first_name,
                    'patronymic': user.patronymic,
                    'tab_number': user.tab_number or '—',
                    'employee_code': user.employee_code_1c or '—',
                    'department': user.department.name if user.department else '—',
                    'email': user.corporate_email or user.personal_email or '—',
                })
            
            return JsonResponse({'users': users_data})
        
        # Обычный поиск подразделений
        query = request.GET.get('q', '').strip()
        logger.info(f'search_departments query: {query!r}')
        
        if not query:
            return JsonResponse({'departments': []})
        
        departments = Department.objects.filter(
            name__icontains=query,
            is_active=True,
        ).annotate(
            users_count=Count('employees', filter=~Q(employees__is_fired=True))
        ).order_by('name')[:20]
        
        logger.info(f'search_departments found: {len(departments)}')
        
        departments_data = []
        for dept in departments:
            departments_data.append({
                'id': dept.id,
                'name': dept.name,
                'code_1c': dept.code_1c or '—',
                'users_count': dept.users_count,
            })
        
        return JsonResponse({'departments': departments_data})
    except Exception as e:
        logger.error(f'search_departments error: {e}')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def training_add_users_by_departments(request, pk):
    """AJAX: Добавить сотрудников выбранных подразделений в обучение."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    training = get_object_or_404(Training, pk=pk)
    department_ids = request.POST.getlist('department_ids[]') or request.POST.getlist('department_ids', [])
    
    if not department_ids:
        return JsonResponse({'error': 'No departments selected'}, status=400)
    
    # Get existing user IDs in this training
    existing_user_ids = set(training.enrollments.values_list('user_id', flat=True))
    
    # Get users from selected departments
    departments = Department.objects.filter(
        id__in=department_ids,
        is_active=True,
    )
    
    users_to_add = User.objects.filter(
        department__in=departments,
        is_active=True,
        is_fired=False,
    ).exclude(
        id__in=existing_user_ids
    ).order_by('last_name', 'first_name')
    
    added = []
    already_enrolled = []
    errors = []
    
    for user in users_to_add:
        try:
            enrollment = TrainingEnrollment.objects.create(
                user=user,
                training=training,
                status=TrainingEnrollment.Status.NOT_STARTED,
                group=training.group,
            )
            added.append({
                'id': user.id,
                'name': user.get_full_name(),
                'department': user.department.name if user.department else '—',
                'tab_number': user.tab_number or '—',
                'enrollment_id': enrollment.pk,
            })
        except Exception as e:
            logger.error(f'Error adding user {user.get_full_name()}: {e}')
            errors.append({
                'user': user.get_full_name(),
                'error': str(e),
            })
    
    # Get users that were already enrolled
    for dept in departments:
        dept_users = User.objects.filter(
            department=dept,
            is_active=True,
            is_fired=False,
        ).filter(
            id__in=existing_user_ids
        )
        for user in dept_users:
            already_enrolled.append({
                'id': user.id,
                'name': user.get_full_name(),
                'department': dept.name,
            })
    
    return JsonResponse({
        'status': 'ok',
        'added': added,
        'already_enrolled': already_enrolled,
        'errors': errors,
        'added_count': len(added),
        'already_count': len(already_enrolled),
        'error_count': len(errors),
    })


@login_required
def training_add_user(request, pk):
    """AJAX: Добавить пользователя в обучение и назначить на курс Skillspace."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    training = get_object_or_404(Training, pk=pk)
    user_id = request.POST.get('user_id')
    
    if not user_id:
        return JsonResponse({'error': 'user_id required'}, status=400)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    # Check if already enrolled
    existing = training.enrollments.filter(user=user).first()
    if existing:
        return JsonResponse({
            'error': 'User already enrolled',
            'already_enrolled': True,
        })
    
    # Create enrollment
    enrollment = TrainingEnrollment.objects.create(
        user=user,
        training=training,
        status=TrainingEnrollment.Status.NOT_STARTED,
        group=training.group,
    )
    
    return JsonResponse({
        'status': 'ok',
        'user_name': user.get_full_name(),
        'tab_number': user.tab_number or '—',
        'department': user.department.name if user.department else '—',
        'email': user.corporate_email or user.personal_email or '—',
        'enrollment_id': enrollment.pk,
    })


@login_required
def training_assign_course(request, pk, user_id):
    """AJAX: Назначить сотрудника на курс Skillspace."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    training = get_object_or_404(Training, pk=pk)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    # Check if enrollment exists
    enrollment = training.enrollments.filter(user=user).first()
    if not enrollment:
        return JsonResponse({
            'error': 'User not enrolled in training',
            'not_enrolled': True,
        })
    
    # Check if course ID is configured
    if not training.training_type.skillspace_course_id:
        return JsonResponse({
            'error': 'Не указан ID курса на Skillspace',
            'no_course_id': True,
        })
    
    email = user.corporate_email or user.personal_email
    if not email:
        return JsonResponse({
            'error': 'Нет email у сотрудника',
            'no_email': True,
        })
    
    try:
        # Use group_id from training (not enrollment)
        group_id = training.group.skillspace_id if training.group else ''
        client = SkillspaceClient()
        result = client.invite_student(
            email=email,
            course_id=training.training_type.skillspace_course_id,
            first_name=user.first_name,
            last_name=user.last_name,
            patronymic=user.patronymic,
            comment=f'Табельный номер: {user.tab_number}' if user.tab_number else '',
            disable_notification=True,
            group_id=group_id,
        )
        
        # Empty response = user already enrolled in course on platform (reenrolled)
        if result == {}:
            logger.info(f'User {user.get_full_name()} re-enrolled in course on platform')
            enrollment.status = TrainingEnrollment.Status.IN_PROGRESS
            enrollment.display_status = TrainingEnrollment.DisplayStatus.COURSE_STARTED
            enrollment.save(update_fields=['status', 'display_status'])
            return JsonResponse({
                'status': 'ok',
                'reenrolled': True,
                'user_name': user.get_full_name(),
            })
        
        logger.info(f'Successfully assigned {user.get_full_name()} to course')
        enrollment.status = TrainingEnrollment.Status.IN_PROGRESS
        enrollment.display_status = TrainingEnrollment.DisplayStatus.COURSE_STARTED
        enrollment.save(update_fields=['status', 'display_status'])
        
        return JsonResponse({
            'status': 'ok',
            'user_name': user.get_full_name(),
        })
        
    except SkillspaceAPIError as e:
        logger.error(f'Failed to assign {user.get_full_name()} to Skillspace: {e}')
        return JsonResponse({
            'error': str(e),
        }, status=500)


@login_required
def training_remove_user(request, pk, user_id):
    """AJAX: Удалить пользователя из обучения."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    training = get_object_or_404(Training, pk=pk)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    enrollment = training.enrollments.filter(user=user).first()
    if enrollment:
        enrollment.delete()
        return JsonResponse({'status': 'ok'})
    
    return JsonResponse({'error': 'Enrollment not found'}, status=404)


@login_required
def training_bulk_remove(request, pk):
    """AJAX: Массовое удаление пользователей из обучения."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    training = get_object_or_404(Training, pk=pk)
    user_ids = request.POST.getlist('user_ids[]') or request.POST.getlist('user_ids', [])
    
    if not user_ids:
        return JsonResponse({'error': 'No users selected'}, status=400)
    
    removed_count = 0
    not_found_count = 0
    
    # Удаление из базы данных
    for user_id in user_ids:
        try:
            user = User.objects.get(id=user_id)
            enrollment = training.enrollments.filter(user=user).first()
            if enrollment:
                enrollment.delete()
                removed_count += 1
            else:
                not_found_count += 1
        except User.DoesNotExist:
            not_found_count += 1
    
    return JsonResponse({
        'status': 'ok',
        'removed_count': removed_count,
        'not_found_count': not_found_count,
    })


@login_required
def training_check_progress(request, pk):
    """AJAX: Проверить прогресс обучения (синхронизировать с Skillspace)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    training = get_object_or_404(Training, pk=pk)
    
    # For now, just return current stats
    # In future, this could call Skillspace API to get latest progress
    total = training.enrollments.count()
    completed = training.enrollments.filter(status='completed').count()
    in_progress = training.enrollments.filter(status='in_progress').count()
    not_started = training.enrollments.filter(status='not_started').count()
    failed = training.enrollments.filter(status='failed').count()
    
    return JsonResponse({
        'status': 'ok',
        'total': total,
        'completed': completed,
        'in_progress': in_progress,
        'not_started': not_started,
        'failed': failed,
        'completion_rate': training.completion_rate,
    })


@login_required
def training_invite_link(request, pk):
    """Получить ссылку для приглашения на обучение."""
    training = get_object_or_404(Training, pk=pk)
    
    if not training.training_type.skillspace_course_id:
        return JsonResponse({'error': 'Не указан ID курса на Skillspace'}, status=400)
    
    course_id = training.training_type.skillspace_course_id
    api_key = settings.SKILLSPACE_API_KEY
    
    # Generate invite link
    invite_url = (
        f'https://{settings.SKILLSPACE_SCHOOL_DOMAIN}/api/rest/open/v1/'
        f'course/student-invite?token={api_key}&courses[{course_id}]=247759'
    )
    
    return JsonResponse({
        'status': 'ok',
        'invite_url': invite_url,
        'course_id': course_id,
    })


@csrf_exempt
def training_webhook(request):
    """
    Webhook endpoint for receiving events from Skillspace.
    
    Receives webhook callbacks when students complete courses, pass tests, etc.
    URL: /training/webhooks/
    
    Skillspace sends:
    {
      "name": "course-begin",
      "student": {"email": "user@example.com"},
      "course": {"uuid": "xxx-xxx-xxx"}
    }
    """
    # ===== DETAIL LOGGING =====
    webhook_log = logging.getLogger('webhook')
    webhook_log.info('=' * 80)
    webhook_log.info(f'INCOMING | {request.method} {request.get_full_path()}')
    webhook_log.info(f'IP: {request.META.get("REMOTE_ADDR")}')
    webhook_log.info(f'Headers: {dict(request.headers)}')
    raw_body = request.body.decode('utf-8', errors='replace')
    webhook_log.info(f'Body: {raw_body}')
    
    if request.method != 'POST':
        resp = JsonResponse({'error': 'Method not allowed'}, status=405)
        webhook_log.info(f'RESPONSE | {resp.status_code} | {resp.content.decode()}')
        webhook_log.info('=' * 80)
        return resp

    try:
        payload = json.loads(raw_body)
        webhook_log.info(f'Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}')
    except (json.JSONDecodeError, ValueError) as e:
        webhook_log.error(f'JSON Error: {e}')
        resp = JsonResponse({'error': 'Invalid JSON'}, status=400)
        webhook_log.info(f'RESPONSE | {resp.status_code} | {resp.content.decode()}')
        webhook_log.info('=' * 80)
        return resp

    # Extract data from payload
    event_name = payload.get('name', '')
    student_email = payload.get('student', {}).get('email', '')
    student_uuid = payload.get('student', {}).get('uuid', '')
    course_uuid = payload.get('course', {}).get('uuid', '')
    
    webhook_log.info(f'Extracted: event={event_name}, email={student_email}, uuid={student_uuid}, course={course_uuid}')

    # Save UUID for "course-begin" event (Пользователь начал курс)
    if event_name == 'course-begin' and student_uuid and student_email:
        user = User.objects.filter(
            Q(corporate_email=student_email) |
            Q(personal_email=student_email)
        ).first()
        if user:
            webhook_log.info(f'User found: {user.get_full_name()} (pk={user.pk}, uuid_skillspace={user.uuid_skillspace})')
            if not user.uuid_skillspace:
                user.uuid_skillspace = student_uuid
                user.save(update_fields=['uuid_skillspace'])
                webhook_log.info(f'Saved UUID for {user.get_full_name()}: {student_uuid}')
            else:
                webhook_log.info(f'UUID already set for {user.get_full_name()}: {user.uuid_skillspace}')
        else:
            webhook_log.warning(f'User not found for email {student_email} (UUID: {student_uuid})')

    # Find training by course UUID
    training = Training.objects.filter(
        training_type__skillspace_course_id=course_uuid
    ).first()

    if not training and student_uuid:
        # Fallback: find training by user's enrollments and skillspace_course_id
        user = User.objects.filter(uuid_skillspace=student_uuid).first()
        if user:
            enrollments = TrainingEnrollment.objects.filter(user=user).select_related('training')
            for enr in enrollments:
                tt = enr.training.training_type
                if tt.skillspace_course_id:
                    training = enr.training
                    course_uuid = tt.skillspace_course_id
                    webhook_log.info(f'Fallback: found training {training.pk} via user {user.pk} enrollment')
                    break

    if not training:
        webhook_log.warning(f'Training not found for course UUID {course_uuid}')
        resp = JsonResponse({'status': 'not_found', 'message': 'Training not found'}, status=200)
        webhook_log.info(f'RESPONSE | {resp.status_code} | {resp.content.decode()}')
        webhook_log.info('=' * 80)
        return resp

    webhook_log.info(f'Training found: {training.pk} - {training.title}')

    # Find enrollment - first by uuid, then by email
    enrollment = None
    user = None
    
    if student_uuid:
        # Try to find user by uuid_skillspace
        user = User.objects.filter(uuid_skillspace=student_uuid).first()
        if user:
            webhook_log.info(f'User by uuid_skillspace: {user.get_full_name()} (pk={user.pk})')
            enrollment = TrainingEnrollment.objects.filter(
                training=training,
                user=user,
            ).first()
    
    # If not found by uuid, try by email
    if not enrollment and student_email:
        enrollment = TrainingEnrollment.objects.filter(
            training=training,
            user__corporate_email=student_email,
        ).first()
    
    if not enrollment and student_email:
        enrollment = TrainingEnrollment.objects.filter(
            training=training,
            user__personal_email=student_email,
        ).first()

    if not enrollment:
        webhook_log.warning(f'Enrollment not found for email {student_email} in training {training.pk}')
        resp = JsonResponse({'status': 'not_found'}, status=200)
        webhook_log.info(f'RESPONSE | {resp.status_code} | {resp.content.decode()}')
        webhook_log.info('=' * 80)
        return resp

    webhook_log.info(f'Enrollment: {enrollment.pk} | User: {enrollment.user.get_full_name()} | Status: {enrollment.status} -> {event_name}')

    # Update enrollment based on event
    if event_name == 'course-end':
        # Course completed
        # Save UUID to user if not present
        if student_uuid and enrollment.user and not enrollment.user.uuid_skillspace:
            enrollment.user.uuid_skillspace = student_uuid
            enrollment.user.save(update_fields=['uuid_skillspace'])
            webhook_log.info(f'Saved UUID for {enrollment.user.get_full_name()}: {student_uuid}')
        elif student_uuid and enrollment.user:
            webhook_log.info(f'User UUID already set: {enrollment.user.uuid_skillspace}')

        old_status = enrollment.status
        enrollment.status = TrainingEnrollment.Status.COMPLETED
        enrollment.display_status = TrainingEnrollment.DisplayStatus.COMPLETED_SUCCESS
        
        lesson = payload.get('lesson', {})
        if lesson and 'score' in lesson:
            enrollment.score = lesson['score']
        
        # Try to parse date from payload
        event_date = payload.get('date')
        if event_date:
            try:
                dt = timezone.datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                # fromisoformat returns aware datetime when timezone info is present
                if dt.tzinfo is None:
                    dt = timezone.make_aware(dt)
                enrollment.completed_at = dt
                webhook_log.info(f'Parsed event date: {event_date}')
            except (ValueError, TypeError) as e:
                webhook_log.warning(f'Failed to parse date "{event_date}": {e}')
                enrollment.completed_at = timezone.now()
        else:
            enrollment.completed_at = timezone.now()
            webhook_log.info('No date in payload, using now')
        
        enrollment.save(update_fields=['status', 'display_status', 'score', 'completed_at'])
        webhook_log.info(f'Course completed for {enrollment.user.get_full_name()} | Status: {old_status} -> {enrollment.status} | Completed at: {enrollment.completed_at}')

    elif event_name == 'session-begin':
        # Session started
        if student_uuid and enrollment.user:
            if not enrollment.user.uuid_skillspace:
                enrollment.user.uuid_skillspace = student_uuid
                enrollment.user.save(update_fields=['uuid_skillspace'])
                webhook_log.info(f'Saved UUID for {enrollment.user.get_full_name()}: {student_uuid}')
            else:
                webhook_log.info(f'UUID already set for {enrollment.user.get_full_name()}: {enrollment.user.uuid_skillspace}')
        
        old_status = enrollment.status
        if enrollment.status == TrainingEnrollment.Status.NOT_STARTED:
            enrollment.status = TrainingEnrollment.Status.IN_PROGRESS
            enrollment.display_status = TrainingEnrollment.DisplayStatus.COURSE_STARTED
            enrollment.save(update_fields=['status', 'display_status'])
            webhook_log.info(f'Session started for {enrollment.user.get_full_name()} | Status: {old_status} -> {enrollment.status}')
        else:
            webhook_log.info(f'Session already started for {enrollment.user.get_full_name()} | Current: {enrollment.status}')

    elif event_name == 'course-begin':
        # Course started
        old_status = enrollment.status
        if enrollment.status == TrainingEnrollment.Status.NOT_STARTED:
            enrollment.status = TrainingEnrollment.Status.IN_PROGRESS
            enrollment.display_status = TrainingEnrollment.DisplayStatus.COURSE_STARTED
            enrollment.save(update_fields=['status', 'display_status'])
            webhook_log.info(f'Course started for {enrollment.user.get_full_name()} | Status: {old_status} -> {enrollment.status}')
        else:
            webhook_log.info(f'Course already started for {enrollment.user.get_full_name()} | Current: {enrollment.status}')

    else:
        webhook_log.info(f'Unhandled event: {event_name} for {enrollment.user.get_full_name()}')

    resp = JsonResponse({'status': 'ok'})
    webhook_log.info(f'RESPONSE | {resp.status_code} | {resp.content.decode()}')
    webhook_log.info('=' * 80)
    return resp


@login_required
def sync_all_trainings(request):
    """Синхронизация всех активных обучений с Skillspace."""
    synced = 0
    errors = 0

    for training in Training.objects.filter(is_active=True, status=Training.Status.PENDING):
        try:
            result = sync_training_to_skillspace(training)
            if 'error' not in result:
                synced += 1
            else:
                errors += 1
        except Exception as e:
            logger.error(f'Sync error for training {training.pk}: {e}')
            errors += 1

    if errors:
        messages.warning(request, f'Синхронизировано {synced}, ошибок: {errors}')
    else:
        messages.success(request, f'Синхронизировано {synced} обучений')

    return redirect('training:type_list')


# ============================================================================
# Reports
# ============================================================================

@login_required
def training_report(request):
    """Отчёт по прохождению обучения."""
    # Filter params
    training_type = request.GET.get('type')
    department = request.GET.get('department')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    # Base queryset
    trainings = Training.objects.select_related('training_type').filter(is_active=True)

    if training_type:
        trainings = trainings.filter(training_type_id=training_type)
    if date_from:
        trainings = trainings.filter(start_date__gte=date_from)
    if date_to:
        trainings = trainings.filter(end_date__lte=date_to)

    enrollments = TrainingEnrollment.objects.filter(
        training__in=trainings
    ).select_related('user', 'user__department', 'training', 'training__training_type')

    if department:
        enrollments = enrollments.filter(user__department_id=department)
    if status:
        enrollments = enrollments.filter(status=status)

    enrollments = enrollments.order_by('training__training_type__name', 'user__last_name')

    # Summary stats
    total = enrollments.count()
    completed = enrollments.filter(status='completed').count()
    not_completed = enrollments.filter(status__in=['not_started', 'in_progress', 'failed']).count()
    failed = enrollments.filter(status='failed').count()

    # Department breakdown
    dept_stats = {}
    for dept in Department.objects.filter(is_active=True):
        dept_enrollments = enrollments.filter(user__department=dept)
        dept_total = dept_enrollments.count()
        if dept_total > 0:
            dept_completed = dept_enrollments.filter(status='completed').count()
            dept_stats[dept.name] = {
                'total': dept_total,
                'completed': dept_completed,
                'not_completed': dept_total - dept_completed,
                'rate': round(dept_completed / dept_total * 100) if dept_total else 0,
            }

    # Training type breakdown
    type_stats = {}
    for tt in TrainingType.objects.filter(is_active=True):
        tt_enrollments = enrollments.filter(training__training_type=tt)
        tt_total = tt_enrollments.count()
        if tt_total > 0:
            tt_completed = tt_enrollments.filter(status='completed').count()
            type_stats[tt.name] = {
                'total': tt_total,
                'completed': tt_completed,
                'not_completed': tt_total - tt_completed,
                'rate': round(tt_completed / tt_total * 100) if tt_total else 0,
            }

    context = {
        'enrollments': enrollments,
        'total': total,
        'completed': completed,
        'not_completed': not_completed,
        'failed': failed,
        'dept_stats': dept_stats,
        'type_stats': type_stats,
        'departments': Department.objects.filter(is_active=True),
        'training_types': TrainingType.objects.filter(is_active=True),
        'current_type': training_type,
        'current_department': department,
        'current_status': status,
        'current_date_from': date_from,
        'current_date_to': date_to,
    }
    return render(request, 'training/report.html', context)


# ============================================================================
# Training Goals (CRUD)
# ============================================================================

@login_required
def training_goal_list(request):
    """Список целей обучения."""
    query = request.GET.get('q', '').strip()

    goals = TrainingGoal.objects.all()
    if query:
        goals = goals.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    goals = goals.order_by('name')

    return render(request, 'training/goal_list.html', {
        'goals': goals,
        'query': query,
    })


@login_required
def training_goal_create(request):
    """Создание цели обучения."""
    if request.method == 'POST':
        form = TrainingGoalForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Цель обучения создана')
            return redirect('training:goal_list')
    else:
        form = TrainingGoalForm()

    return render(request, 'training/goal_form.html', {
        'form': form,
        'action': 'Создание',
    })


@login_required
def training_goal_edit(request, pk):
    """Редактирование цели обучения."""
    goal = get_object_or_404(TrainingGoal, pk=pk)

    if request.method == 'POST':
        form = TrainingGoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, 'Цель обучения обновлена')
            return redirect('training:goal_list')
    else:
        form = TrainingGoalForm(instance=goal)

    return render(request, 'training/goal_form.html', {
        'form': form,
        'goal': goal,
        'action': 'Редактирование',
    })


@login_required
def training_goal_delete(request, pk):
    """Удаление цели обучения."""
    goal = get_object_or_404(TrainingGoal, pk=pk)

    if request.method == 'POST':
        goal.delete()
        messages.success(request, 'Цель обучения удалена')
        return redirect('training:goal_list')

    return render(request, 'training/goal_confirm_delete.html', {
        'obj': goal,
    })


# ============================================================================
# Training Journal
# ============================================================================

@login_required
def training_journal(request):
    """Журнал обучения сотрудников."""
    # Get filter parameters
    goal_id = request.GET.get('goal', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    show_without = request.GET.get('show_without', 'false').lower() == 'true'

    # Default period: current year
    now = timezone.now()
    default_date_from = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    default_date_to = now

    if not date_from:
        date_from = default_date_from.strftime('%Y-%m-%d')
    if not date_to:
        date_to = default_date_to.strftime('%Y-%m-%d')

    # Parse dates
    try:
        date_from_obj = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to_obj = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
    except ValueError:
        date_from_obj = default_date_from.date()
        date_to_obj = default_date_to.date()

    # Get goals
    goals = TrainingGoal.objects.filter(is_active=True).order_by('name')
    goal = None
    if goal_id:
        try:
            goal = TrainingGoal.objects.get(pk=goal_id, is_active=True)
        except TrainingGoal.DoesNotExist:
            goal = None

    # Build journal data
    journal_data = []
    without_trainings = []
    in_progress_data = []
    not_started_data = []

    if goal:
        # Get all training types linked to this goal (including archived)
        training_types = goal.training_types.all()

        if training_types.exists():
            # Get all trainings for these types
            trainings = Training.objects.filter(
                training_type__in=training_types,
                is_active=True,
            ).select_related('training_type')

            # Get all enrollments for these trainings
            enrollments = TrainingEnrollment.objects.filter(
                training__in=trainings,
            ).select_related(
                'user', 'user__department', 'training', 'training__training_type', 'assigned_by'
            )

            # Completed enrollments within the period
            # Use timezone-aware datetime comparison instead of __date
            from datetime import datetime
            dt_from = timezone.make_aware(datetime.combine(date_from_obj, datetime.min.time()))
            dt_to = timezone.make_aware(datetime.combine(date_to_obj, datetime.max.time()))
            
            completed_enrollments = enrollments.filter(
                status='completed',
                completed_at__gte=dt_from,
                completed_at__lte=dt_to,
            ).distinct()

            # Get user IDs who completed training in this period
            completed_user_ids = set(
                completed_enrollments.values_list('user_id', flat=True)
            )

            # Build journal entries for completed
            for enrollment in completed_enrollments:
                # Find previous successful completion for this user and training type
                previous_completion = TrainingEnrollment.objects.filter(
                    user=enrollment.user,
                    training__training_type=enrollment.training.training_type,
                    status='completed',
                    completed_at__lt=enrollment.completed_at,
                ).order_by('-completed_at').first()
                
                journal_data.append({
                    'user': enrollment.user,
                    'training_title': enrollment.training.title,
                    'training_type_name': enrollment.training.training_type.name,
                    'completed_at': enrollment.completed_at,
                    'previous_completed_at': previous_completion.completed_at if previous_completion else None,
                    'enrolled_at': enrollment.enrolled_at,
                    'score': enrollment.score,
                    'status': enrollment.status,
                    'assigned_by': enrollment.assigned_by,
                })

            # Sort by user last name
            journal_data.sort(key=lambda x: (x['user'].last_name, x['user'].first_name))

            # In progress enrollments (started but not completed)
            in_progress_enrollments = enrollments.filter(
                status='in_progress',
            ).distinct()

            for enrollment in in_progress_enrollments:
                in_progress_data.append({
                    'user': enrollment.user,
                    'training_title': enrollment.training.title,
                    'training_type_name': enrollment.training.training_type.name,
                    'enrolled_at': enrollment.enrolled_at,
                    'score': enrollment.score,
                    'status': enrollment.status,
                    'assigned_by': enrollment.assigned_by,
                })

            in_progress_data.sort(key=lambda x: (x['user'].last_name, x['user'].first_name))

            # Not started enrollments (assigned but not started)
            not_started_enrollments = enrollments.filter(
                status='not_started',
            ).distinct()

            for enrollment in not_started_enrollments:
                not_started_data.append({
                    'user': enrollment.user,
                    'training_title': enrollment.training.title,
                    'training_type_name': enrollment.training.training_type.name,
                    'enrolled_at': enrollment.enrolled_at,
                    'status': enrollment.status,
                    'assigned_by': enrollment.assigned_by,
                })

            not_started_data.sort(key=lambda x: (x['user'].last_name, x['user'].first_name))

            # Get all active employees (excluding fired)
            all_employees = User.objects.filter(
                is_fired=False,
            ).select_related('department').order_by('last_name', 'first_name')

            # Find employees without training in this period
            if show_without:
                for employee in all_employees:
                    if employee.id not in completed_user_ids:
                        without_trainings.append({
                            'user': employee,
                            'has_any_training': TrainingEnrollment.objects.filter(
                                user=employee,
                                training__training_type__in=training_types,
                                status='completed',
                            ).exists(),
                        })

    # Stats
    total_completed = len(journal_data)
    total_in_progress = len(in_progress_data)
    total_not_started = len(not_started_data)
    total_without = len(without_trainings)

    context = {
        'goals': goals,
        'goal': goal,
        'date_from': date_from,
        'date_to': date_to,
        'journal_data': journal_data,
        'in_progress_data': in_progress_data,
        'not_started_data': not_started_data,
        'without_trainings': without_trainings,
        'show_without': show_without,
        'total_completed': total_completed,
        'total_in_progress': total_in_progress,
        'total_not_started': total_not_started,
        'total_without': total_without,
        'default_date_from': default_date_from.strftime('%Y-%m-%d'),
        'default_date_to': default_date_to.strftime('%Y-%m-%d'),
    }
    return render(request, 'training/journal.html', context)

@login_required
def training_list(request):
    """Главная страница — перенаправление на типы обучения."""
    return redirect('training:type_list')


@login_required
def training_list_by_type(request, type_pk):
    """Список обучений для типа."""
    training_type = get_object_or_404(TrainingType, pk=type_pk)
    trainings = Training.objects.filter(
        training_type=training_type,
        is_active=True
    ).order_by('-created_at')
    
    # Fetch groups from Skillspace API if course is configured
    groups = []
    if training_type.skillspace_course_id:
        try:
            client = SkillspaceClient()
            groups = client.get_groups_by_course(training_type.skillspace_course_id)
        except SkillspaceAPIError as e:
            logger.error(f'Failed to load groups for course {training_type.skillspace_course_id}: {e}')
    
    return render(request, 'training/training_list.html', {
        'training_type': training_type,
        'trainings': trainings,
        'groups': groups,
    })


@login_required
def training_create(request, type_pk):
    """Создание назначения обучения."""
    training_type = get_object_or_404(TrainingType, pk=type_pk)
    
    # Sync groups from API before showing form
    if training_type.skillspace_course_id:
        SkillspaceGroup.sync_from_api(training_type.skillspace_course_id)
    
    if request.method == 'POST':
        form = TrainingForm(request.POST)
        if form.is_valid():
            training = form.save(commit=False)
            training.training_type = training_type
            training.save()
            
            messages.success(request, f'Обучение "{training.title}" создано')
            return redirect('training:type_trainings', type_pk=type_pk)
    else:
        form = TrainingForm(initial={'training_type': training_type.pk})
    
    return render(request, 'training/training_form.html', {
        'form': form,
        'training_type': training_type,
        'action': 'Создание',
    })


# ============================================================================
# Action 360 Report Upload
# ============================================================================

# Mapping of Excel status strings to TrainingEnrollment.Status codes
STATUS_MAPPING = {
    'не начито': 'not_started',
    'неначато': 'not_started',
    'not started': 'not_started',
    'программа не начата': 'not_started',
    'в процессе': 'in_progress',
    'впроцессе': 'in_progress',
    'in progress': 'in_progress',
    'учится по плану': 'in_progress',
    'учится по плану': 'in_progress',
    'отстает от плана': 'in_progress',
    'completed': 'completed',
    'программа завершена': 'completed',
    'пройдено': 'completed',
    'пройдена': 'completed',
    'пройдено_успешно': 'completed',
    'успешно': 'completed',
    'не пройдено': 'failed',
    'непройдено': 'failed',
    'не_пройдено': 'failed',
    'failed': 'failed',
    'не пройдена': 'failed',
}


def _normalize_status(status_str):
    """Normalize status string from Excel to TrainingEnrollment.Status code."""
    if not status_str:
        return 'not_started'
    key = str(status_str).strip().lower()
    return STATUS_MAPPING.get(key, 'not_started')


def _find_user_by_full_name(full_name):
    """Search for user by full name parts."""
    if not full_name:
        return None
    parts = full_name.strip().split()
    if not parts:
        return None

    # Build query: at minimum last_name and first_name
    query = Q()
    if len(parts) >= 3:
        query = Q(
            last_name__iexact=parts[0],
            first_name__iexact=parts[1],
        )
        # Try with patronymic match
        patronymic_match = Q(patronymic__iexact=parts[2])
        user = User.objects.filter(query & patronymic_match).exclude(is_fired=True).first()
        if user:
            return user
        # Try without patronymic
        user = User.objects.filter(query).exclude(is_fired=True).first()
        if user:
            return user
    elif len(parts) == 2:
        query = Q(
            last_name__iexact=parts[0],
            first_name__iexact=parts[1],
        )
        user = User.objects.filter(query).exclude(is_fired=True).first()
        if user:
            return user
        # Try partial patronymic
        user = User.objects.filter(
            last_name__iexact=parts[0],
            first_name__icontains=parts[1],
        ).exclude(is_fired=True).first()
        if user:
            return user
    else:
        # Single name - search anywhere
        user = User.objects.filter(
            Q(last_name__iexact=parts[0]) |
            Q(first_name__iexact=parts[0])
        ).exclude(is_fired=True).first()
        if user:
            return user

    return None


def _find_assigner_by_full_name(full_name):
    """Search for assigner user by full name (last_name first_name format)."""
    if not full_name:
        return None
    parts = full_name.strip().split()
    if not parts:
        return None
    if len(parts) >= 2:
        return User.objects.filter(
            last_name__iexact=parts[0],
            first_name__iexact=parts[1],
            is_fired=False,
        ).first()
    return User.objects.filter(
        Q(last_name__iexact=parts[0]) | Q(first_name__iexact=parts[0])
    ).exclude(is_fired=True).first()


def _find_or_create_goal(goal_name):
    """Find or create TrainingGoal."""
    if not goal_name:
        return None
    goal_name = str(goal_name).strip()
    if not goal_name:
        return None
    return TrainingGoal.objects.get_or_create(name=goal_name)[0]


def _find_training_for_goal(goal, request_user):
    """Find or create a Training for the given goal."""
    if not goal:
        return None

    # Find TrainingType linked to this goal
    training_types = goal.training_types.filter(is_active=True)
    if not training_types.exists():
        # Create a new TrainingType for this goal
        training_type = TrainingType.objects.create(
            name=goal.name,
            description=f'Курс, созданный из отчета Актион360 для цели: {goal.name}',
        )
        goal.training_types.add(training_type)
        training_types = TrainingType.objects.filter(pk=training_type.pk)

    training_type = training_types.first()

    # Find or create Training
    training = Training.objects.filter(
        training_type=training_type,
        title=goal.name,
        is_active=True,
    ).first()

    if not training:
        training = Training.objects.create(
            training_type=training_type,
            title=goal.name,
            description=f'Обучение, созданное из отчета Актион360',
            status=Training.Status.ACTIVE,
        )

    return training


@login_required
def upload_action_report(request):
    """Загрузка отчета Актион360 (Excel .xlsx)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    file = request.FILES.get('report_file')
    if not file:
        return JsonResponse({'error': 'Файл не выбран'}, status=400)

    if not file.name.endswith('.xlsx'):
        return JsonResponse({'error': 'Поддерживаются только файлы .xlsx'}, status=400)

    results = {
        'total': 0,
        'processed': 0,
        'users_found': 0,
        'users_not_found': 0,
        'emails_updated': 0,
        'phones_updated': 0,
        'goals_created': 0,
        'trainings_type_created': 0,
        'trainings_created': 0,
        'enrollments_created': 0,
        'enrollments_updated': 0,
        'assigners_found': 0,
        'errors': [],
        'warnings': [],
    }
    seen_rows = set()

    try:
        wb = openpyxl.load_workbook(file)
        ws = wb.active

        if ws is None:
            return JsonResponse({'error': 'Лист книги пуст'}, status=400)

        # Find header row by scanning all rows for "ФИО" or similar
        header_row_idx = None
        for r in range(1, min(ws.max_row + 1, 50)):
            row_vals = [str(cell.value).strip() if cell.value else '' for cell in ws[r]]
            for v in row_vals:
                v_lower = v.lower()
                if 'фио' in v_lower or 'фамилия' in v_lower:
                    header_row_idx = r
                    break
            if header_row_idx:
                break

        if header_row_idx is None:
            return JsonResponse({
                'error': 'Не найдена строка с заголовками (столбец ФИО)'
            }, status=400)

        # Read headers from found row
        headers = []
        for cell in ws[header_row_idx]:
            headers.append(str(cell.value).strip() if cell.value else '')

        def find_column(*candidates):
            """Find column index by multiple possible names."""
            for i, h in enumerate(headers):
                if h:
                    h_lower = h.lower()
                    for c in candidates:
                        if c.lower() in h_lower:
                            return i
            return None

        col_fio = find_column('фио', 'фамилия имя отчество', 'full name', 'сотрудник')
        col_email = find_column('электронная почта', 'email', 'почта', 'e-mail')
        col_phone = find_column('телефон', 'mobile', 'мобильный')
        col_groups = find_column('группы')
        col_program = find_column('название программы', 'программы')
        col_assigner = find_column('назначил обучение', 'назначил', 'assigner')
        col_goal = find_column('группа программ и тестов', 'цель обучения', 'training goal')
        col_status = find_column('статус', 'статус обучения', 'status')

        if col_fio is None:
            return JsonResponse({
                'error': 'Не найден столбец ФИО. Ожидаемые названия: ФИО, Фамилия Имя Отчество, Сотрудник'
            }, status=400)

        # Process rows starting after header
        for row_idx, row in enumerate(ws.iter_rows(min_row=header_row_idx + 1, values_only=True), start=header_row_idx + 1):
            results['total'] += 1

            try:
                # Get full name
                fio = row[col_fio] if col_fio < len(row) else None
                if not fio or not str(fio).strip():
                    results['warnings'].append(f'Строка {row_idx}: пропущена (пустое ФИО)')
                    continue

                fio = str(fio).strip()

                # Find user
                user = _find_user_by_full_name(fio)
                if not user:
                    results['users_not_found'] += 1
                    results['errors'].append(f'Строка {row_idx}: сотрудник не найден — {fio}')
                    continue

                results['users_found'] += 1

                # Update personal email if not set
                if col_email is not None and col_email < len(row):
                    email_val = row[col_email]
                    if email_val and str(email_val).strip():
                        email_val = str(email_val).strip()
                        if not user.personal_email:
                            user.personal_email = email_val
                            user.save(update_fields=['personal_email'])
                            results['emails_updated'] += 1

                # Update personal phone if not set
                if col_phone is not None and col_phone < len(row):
                    phone_val = row[col_phone]
                    if phone_val and str(phone_val).strip():
                        phone_val = str(phone_val).strip()
                        if not user.personal_phone:
                            user.personal_phone = phone_val
                            user.save(update_fields=['personal_phone'])
                            results['phones_updated'] += 1

                # Get training type from "Группы" column
                group_name = ''
                if col_groups is not None and col_groups < len(row):
                    group_name = str(row[col_groups]).strip() if row[col_groups] else ''

                # Get training title from "Название программы" column
                program_name = ''
                if col_program is not None and col_program < len(row):
                    program_name = str(row[col_program]).strip() if row[col_program] else ''

                # Get training goal from "Группа программ и тестов" column
                goal_name = ''
                if col_goal is not None and col_goal < len(row):
                    goal_name = str(row[col_goal]).strip() if row[col_goal] else ''

                if not goal_name:
                    results['warnings'].append(f'Строка {row_idx}: {fio} — нет цели обучения, пропуск')
                    continue

                # Skip duplicate rows (same FIO + program_name)
                row_key = f'{fio}|{program_name}'
                if row_key in seen_rows:
                    results['warnings'].append(f'Строка {row_idx}: {fio} — дубликат, пропуск')
                    continue
                seen_rows.add(row_key)

                # Find or create TrainingGoal
                goal = _find_or_create_goal(goal_name)

                # Find or create TrainingType from "Группы"
                training_type = None
                if group_name:
                    training_type, tt_created = TrainingType.objects.get_or_create(
                        name=group_name,
                        defaults={'description': f'Курс, созданный из отчета Актион360'}
                    )
                    if tt_created:
                        results['trainings_type_created'] = results.get('trainings_type_created', 0) + 1

                    # Link TrainingType with TrainingGoal
                    if goal and goal not in training_type.goals.all():
                        training_type.goals.add(goal)

                # Find or create Training from "Название программы"
                training = None
                if training_type and program_name:
                    training, tr_created = Training.objects.get_or_create(
                        training_type=training_type,
                        title=program_name,
                        defaults={
                            'description': f'Обучение, созданное из отчета Актион360',
                            'status': Training.Status.ACTIVE,
                        }
                    )
                    if tr_created:
                        results['trainings_created'] = results.get('trainings_created', 0) + 1

                if not training:
                    results['errors'].append(f'Строка {row_idx}: {fio} — ошибка создания обучения')
                    continue

                # Get status
                status_raw = ''
                if col_status is not None and col_status < len(row):
                    status_raw = str(row[col_status]).strip() if row[col_status] else ''
                status_code = _normalize_status(status_raw)

                # Validate status
                valid_statuses = [s[0] for s in TrainingEnrollment.Status.choices]
                if status_code not in valid_statuses:
                    status_code = 'not_started'

                # Find assigner by full name from Excel
                assigner_name = ''
                assigner = None
                if col_assigner is not None and col_assigner < len(row):
                    assigner_name = str(row[col_assigner]).strip() if row[col_assigner] else ''
                    if assigner_name:
                        assigner = _find_assigner_by_full_name(assigner_name)
                        if assigner:
                            results['assigners_found'] = results.get('assigners_found', 0) + 1

                # Create or update enrollment
                enrollment, created = TrainingEnrollment.objects.get_or_create(
                    training=training,
                    user=user,
                    defaults={
                        'status': status_code,
                        'assigned_by': assigner if assigner else request.user,
                    }
                )

                if not created:
                    # Update existing enrollment
                    changed = False
                    if enrollment.status != status_code:
                        enrollment.status = status_code
                        changed = True
                    if status_code == 'completed':
                        enrollment.completed_at = timezone.now()
                        changed = True
                    if enrollment.assigned_by_id != (assigner.id if assigner else None):
                        enrollment.assigned_by = assigner
                        changed = True
                    if changed:
                        enrollment.save()
                        results['enrollments_updated'] += 1
                else:
                    results['enrollments_created'] += 1

                results['processed'] += 1

            except Exception as e:
                results['errors'].append(f'Строка {row_idx}: {str(e)}')
                logger.error(f'Error processing row {row_idx}: {e}', exc_info=True)

        wb.close()

        return JsonResponse(results)

    except Exception as e:
        logger.error(f'Excel upload error: {e}', exc_info=True)
        return JsonResponse({'error': f'Ошибка обработки файла: {str(e)}'}, status=500)
