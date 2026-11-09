"""
Воркер дедлайнов и эскалаций.

Запускается как фоновый процесс, раз в 30 секунд проверяет:
1. step_runs с истёкшим дедлайном — отправляет напоминание
2. При второй просрочке — эскалация
3. Помечает шаг как закрытый по дедлайну
"""

import time
import logging
import signal
import sys
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from scenarios.models import Run, StepRun, Log
from scenarios.services.executor import ScenarioExecutor
from messaging.services.max_api import MAXClient, MAXAPIError

logger = logging.getLogger(__name__)

_running = True


def _signal_handler(signum, frame):
    global _running
    _running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def run_deadline_worker(interval=30):
    """Запуск воркера дедлайнов."""
    print('=' * 60)
    print('  Сценарии Воркер дедлайнов — Запуск...')
    print('=' * 60)
    print(f'  Интервал проверки: {interval}с')
    print('=' * 60)
    print('')
    print('Воркер запущен. Проверка дедлайнов...')
    print('')
    sys.stdout.flush()

    try:
        while _running:
            try:
                _check_deadlines()
            except Exception as e:
                print(f'ERROR воркера: {e}')
                import traceback
                traceback.print_exc()
                sys.stdout.flush()

            time.sleep(interval)

    except KeyboardInterrupt:
        print('')
        print('Воркер остановлен.')
        print('')


def _check_deadlines():
    """Проверяет все активные run'ы на истечение дедлайнов."""
    # Находим все активные run'ы
    active_runs = Run.objects.filter(status=Run.STATUS_RUNNING)

    for run in active_runs:
        try:
            executor = ScenarioExecutor(run)

            # Находим step_runs с истёкшим дедлайном
            expired = StepRun.objects.filter(
                run=run,
                status=StepRun.STATUS_SENT,
                deadline_at__lt=timezone.now(),
            )

            for step_run in expired:
                _handle_expired(step_run, executor)

        except Exception as e:
            logger.error(f'Ошибка проверки run {run.id}: {e}')


def _handle_expired(step_run: StepRun, executor: ScenarioExecutor):
    """Обрабатывает истёкший дедлайн step_run."""
    step = step_run.step

    # Проверяем, была ли уже эскалация
    if step_run.escalated_at:
        # Вторая просрочка — закрываем шаг
        step_run.status = StepRun.STATUS_EXPIRED
        step_run.save()

        Log.objects.create(
            run=step_run.run,
            event_type=Log.EVENT_DEADLINE_EXPIRED,
            payload_json={
                'step_id': step.id,
                'user_id': step_run.recipient_id,
                'message': 'Закрыт по дедлайну (повторная просрочка)',
            },
        )

        # Ищем следующий шаг
        next_step = executor._find_next_step(step, '')
        if next_step:
            executor._send_next_step(next_step, step_run.recipient_id)

        return

    # Первая просрочка — эскалация
    step_run.escalated_at = timezone.now()
    step_run.save()

    # Отправляем эскалацию
    escalate_to = step.escalate_to_json
    if escalate_to and isinstance(escalate_to, dict):
        _send_escalation(step_run, escalate_to)

    # Отправляем напоминание
    _send_reminder(step_run)

    Log.objects.create(
        run=step_run.run,
        event_type=Log.EVENT_DEADLINE_EXPIRED,
        payload_json={
            'step_id': step.id,
            'user_id': step_run.recipient_id,
            'message': 'Первая просрочка, эскалация отправлена',
        },
    )


def _send_escalation(step_run: StepRun, escalate_to: dict):
    """Отправляет сообщение об эскалации."""
    recipient_id = escalate_to.get('user_id')
    message = escalate_to.get('message', '')

    if not recipient_id:
        return

    try:
        client = MAXClient()
        client.send_message(
            user_id=int(recipient_id),
            text=message,
            format='html',
        )
    except MAXAPIError as e:
        logger.error(f'Ошибка эскалации: {e}')


def _send_reminder(step_run: StepRun):
    """Отправляет напоминание пользователю."""
    step = step_run.step
    user = step_run.recipient

    try:
        client = MAXClient()
        reminder = f'⏰ Напоминание: {step.message_text[:200]}'
        client.send_message(
            user_id=int(user.max_id),
            text=reminder,
            format='html',
        )
    except MAXAPIError as e:
        logger.error(f'Ошибка напоминания: {e}')
