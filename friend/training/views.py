import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.http import JsonResponse, HttpResponse

from accounts.models import User, Department
from .models import TrainingType, Training, TrainingEnrollment
from .forms import TrainingTypeForm, TrainingForm, TrainingUserSelectionForm
from .services.skillspace_api import SkillspaceClient, parse_skillspace_webhook

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


# ============================================================================
# Training Types
# ============================================================================

@login_required
def training_type_list(request):
    """Список типов обучения."""
    types = TrainingType.objects.annotate(
        active_trainings=Count('trainings', filter=Q(trainings__is_active=True)),
        total_enrollments=Count('trainings__enrollments'),
    ).order_by('-is_active', 'name')

    context = {
        'types': types,
    }
    return render(request, 'training/type_list.html', context)


@login_required
def training_type_create(request):
    """Создание типа обучения."""
    if request.method == 'POST':
        form = TrainingTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тип обучения создан')
            return redirect('training:type_list')
    else:
        form = TrainingTypeForm()

    return render(request, 'training/type_form.html', {'form': form, 'action': 'Создание'})


@login_required
def training_type_edit(request, pk):
    """Редактирование типа обучения."""
    obj = get_object_or_404(TrainingType, pk=pk)
    if request.method == 'POST':
        form = TrainingTypeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тип обучения обновлён')
            return redirect('training:type_list')
    else:
        form = TrainingTypeForm(instance=obj)

    return render(request, 'training/type_form.html', {'form': form, 'action': 'Редактирование'})


@login_required
def training_type_delete(request, pk):
    """Удаление типа обучения."""
    obj = get_object_or_404(TrainingType, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Тип обучения удалён')
        return redirect('training:type_list')

    return render(request, 'training/type_confirm_delete.html', {'obj': obj})


# ============================================================================
# Trainings (Instances)
# ============================================================================

@login_required
def training_list_by_type(request, type_pk):
    """Список назначений обучения для типа."""
    training_type = get_object_or_404(TrainingType, pk=type_pk)
    trainings = Training.objects.filter(
        training_type=training_type,
        is_active=True,
    ).select_related('training_type').annotate(
        total_enrollments=Count('enrollments'),
        completed_count=Count('enrollments', filter=Q(enrollments__status='completed')),
    ).order_by('-created_at')

    context = {
        'training_type': training_type,
        'trainings': trainings,
    }
    return render(request, 'training/training_list.html', context)


@login_required
def training_create(request, type_pk):
    """Создание назначения обучения."""
    training_type = get_object_or_404(TrainingType, pk=type_pk)

    if request.method == 'POST':
        form = TrainingForm(request.POST, training_type=training_type)
        if form.is_valid():
            training = form.save()
            training.training_type = training_type
            training.save()

            # Add selected users
            users = form.cleaned_data['users']
            for user in users:
                TrainingEnrollment.objects.get_or_create(
                    training=training,
                    user=user,
                    defaults={'status': TrainingEnrollment.Status.NOT_STARTED},
                )

            messages.success(request, f'Обучение "{training.title}" создано')
            return redirect('training:type_trainings', type_pk=type_pk)
    else:
        form = TrainingForm(training_type=training_type)

    return render(request, 'training/training_form.html', {
        'form': form,
        'training_type': training_type,
        'action': 'Создание',
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

    context = {
        'training': training,
        'enrollments': enrollments,
        'status_filter': status_filter,
        'status_choices': TrainingEnrollment.Status.choices,
    }
    return render(request, 'training/training_detail.html', context)


@login_required
def training_edit(request, pk):
    """Редактирование назначения обучения."""
    training = get_object_or_404(Training, pk=pk)

    if request.method == 'POST':
        form = TrainingForm(request.POST, instance=training)
        if form.is_valid():
            form.save()
            messages.success(request, 'Обучение обновлено')
            return redirect('training:training_detail', pk=training.pk)
    else:
        form = TrainingForm(instance=training)

    return render(request, 'training/training_form.html', {
        'form': form,
        'training': training,
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
    """Синхронизация обучения с Skillspace."""
    training = get_object_or_404(Training, pk=pk)

    try:
        # First sync from Skillspace (get latest data)
        from_result = training.sync_from_skillspace()

        # Then sync to Skillspace (add new students)
        to_result = training.sync_to_skillspace()

        messages.success(request, f'Синхронизация завершена: обновлено {len(from_result["updated"])} записей, добавлено {len(to_result["added"])} студентов')
    except Exception as e:
        logger.error(f'Sync error for training {pk}: {e}')
        messages.error(request, f'Ошибка синхронизации: {str(e)}')

    return redirect('training:training_detail', pk=pk)


@login_required
def training_webhook(request, pk):
    """
    Webhook endpoint for receiving events from Skillspace.
    
    This endpoint receives webhook callbacks from Skillspace platform
    when students complete courses, pass tests, etc.
    """
    training = get_object_or_404(Training, pk=pk)

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        import json
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    parsed = parse_skillspace_webhook(payload)
    event_type = parsed['event_type']
    student_email = parsed['student_email']

    # Find enrollment by email
    enrollment = TrainingEnrollment.objects.filter(
        training=training,
        user__corporate_email=student_email,
    ).first()

    if not enrollment:
        enrollment = TrainingEnrollment.objects.filter(
            training=training,
            user__personal_email=student_email,
        ).first()

    if not enrollment:
        logger.warning(f'Enrollment not found for email {student_email} in training {pk}')
        return JsonResponse({'status': 'not_found'}, status=200)

    # Update enrollment based on event
    if event_type in ('student_completed', 'student_test_passed'):
        enrollment.status = TrainingEnrollment.Status.COMPLETED
        enrollment.score = payload.get('score', 0)
        enrollment.completed_at = timezone.now()
    elif event_type == 'student_failed':
        enrollment.status = TrainingEnrollment.Status.FAILED
        enrollment.score = payload.get('score', 0)
    elif event_type == 'student_started':
        enrollment.status = TrainingEnrollment.Status.IN_PROGRESS

    enrollment.save(update_fields=['status', 'score', 'completed_at'])

    logger.info(f'Webhook processed: {event_type} for {enrollment.user.get_full_name()}')

    return JsonResponse({'status': 'ok'})


@login_required
def sync_all_trainings(request):
    """Синхронизация всех активных обучений с Skillspace."""
    synced = 0
    errors = 0

    for training in Training.objects.filter(is_active=True, status=Training.Status.ACTIVE):
        try:
            training.sync_from_skillspace()
            synced += 1
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
# Main page (redirect to types)
# ============================================================================

@login_required
def training_list(request):
    """Главная страница — перенаправление на типы обучения."""
    return redirect('training:type_list')
