"""
Сервис исполнения сценариев — конечный автомат.

Обрабатывает ответы пользователей, продвигает шаги по ветке,
агрегирует результаты, управляет дедлайнами и эскалациями.
"""

import re
import logging
from datetime import datetime, timedelta, timezone
from django.utils import timezone as django_tz
from django.db import transaction

from scenarios.models import (
    Run, StepRun, Answer, DbValue, Log,
    Step, Branch, Scenario,
)
from accounts.models import User, Department

logger = logging.getLogger(__name__)


class ScenarioExecutor:
    """Конечный автомат для исполнения сценариев."""

    def __init__(self, run: Run):
        self.run = run
        self.context = dict(run.params_json)  # Параметры запуска + агрегаты

    # ========================================================================
    # Запуск сценария
    # ========================================================================

    def start(self):
        """Запуск сценария: создаём step_runs для первого шага каждой ветки."""
        self.run.status = Run.STATUS_RUNNING
        self.run.save(update_fields=['status'])

        # Обновляем текущий запуск для всех получателей
        from scenarios.models import UserCurrentRun
        recipients = set()
        for branch in self.run.scenario.branches.all():
            first_step = branch.steps.filter(
                prev_result_code='',
            ).order_by('step_order').first()
            if first_step:
                recipients.update(self._resolve_mailing_list(first_step))
        
        for recipient in recipients:
            UserCurrentRun.objects.update_or_create(
                user=recipient,
                defaults={'run': self.run},
            )
            logger.info(f'start: set UserCurrentRun for user {recipient.pk} -> run_id={self.run.id}')

        # Лог
        Log.objects.create(
            run=self.run,
            event_type=Log.EVENT_RUN_STARTED,
            payload_json={
                'scenario_id': self.run.scenario_id,
                'scenario_name': str(self.run.scenario),
                'started_by': self.run.started_by_id,
                'params': self.context,
            },
        )

        branches = self.run.scenario.branches.all()
        branch_info = []
        for branch in branches:
            branch_info.append({
                'name': branch.name,
                'code': branch.code,
            })

        Log.objects.create(
            run=self.run,
            event_type=Log.EVENT_RUN_STARTED,
            payload_json={
                'scenario_id': self.run.scenario_id,
                'scenario_name': str(self.run.scenario),
                'started_by': self.run.started_by_id,
                'params': self.context,
                'branches': branch_info,
            },
        )

        for branch in branches:
            self._initialize_branch(branch)

    def _initialize_branch(self, branch: Branch):
        """Инициализация ветки: резолвим mailing_list, создаём step_runs, отправляем сообщения."""
        # Получаем первый шаг ветки (prev_result_code='', минимальный step_order)
        first_step = branch.steps.filter(
            prev_result_code='',
        ).order_by('step_order').first()

        if not first_step:
            logger.warning(f'Нет первого шага для ветки {branch}')
            return

        # Резолвим mailing_list в конкретных сотрудников
        recipients = self._resolve_mailing_list(first_step)

        # Вычитаем exclusion_list
        recipients = self._exclude_list(recipients, first_step)

        # Фильтруем: только пользователи с max_id
        from accounts.models import User as AccountUser
        recipient_ids = [r.pk for r in recipients]
        users_with_max = AccountUser.objects.filter(pk__in=recipient_ids).exclude(max_id__isnull=True).exclude(max_id='')
        recipients = list(users_with_max)
        skipped = len(recipient_ids) - len(recipients)
        if skipped > 0:
            logger.warning(f'Ветка {branch.name}: {skipped} получателей без max_id пропущены')

        logger.info(f'Ветка {branch.name}: {len(recipients)} получателей с max_id')

        # Создаём step_runs и отправляем сообщения для каждого получателя
        for recipient in recipients:
            step_run, created = StepRun.objects.get_or_create(
                run=self.run,
                step=first_step,
                recipient=recipient,
                defaults={
                    'status': StepRun.STATUS_SENT,
                    'deadline_at': self._calc_deadline(first_step),
                },
            )

            # Отправляем сообщение если ещё не отправлено
            if not step_run.sent_at:
                self._send_message_to_user(first_step, recipient.pk, step_run)
                if step_run.sent_at:
                    logger.info(f'Отправлен первый шаг ветки {branch.name} пользователю {recipient.pk}')
                else:
                    logger.warning(f'Не удалось отправить сообщение ветки {branch.name} пользователю {recipient.pk}')
            else:
                logger.info(f'StepRun уже существует для ветки {branch.name} пользователя {recipient.pk}')

    def _send_message_to_user(self, step: Step, user_id: int, step_run: StepRun):
        """Отправляет сообщение пользователю."""
        from accounts.models import User as AccountUser

        user = AccountUser.objects.filter(pk=user_id).first()
        if not user:
            logger.warning(f'Пользователь {user_id} не найден')
            return

        if not user.max_id:
            logger.warning(f'У пользователя {user_id} ({user.get_full_name()}) нет max_id — сообщение не отправлено')
            return

        try:
            message_text = self._substitute_vars(step.message_text)

            # Формируем кнопки из message_json
            buttons = None
            message_json = step.message_json
            if isinstance(message_json, dict):
                msg_type = message_json.get('type', '')
                if msg_type in ('buttons', 'buttons_with_number'):
                    options = message_json.get('options', [])
                    buttons = []
                    for opt in options:
                        buttons.append({
                            'type': 'callback',
                            'text': opt.get('text', ''),
                            'payload': opt.get('result_code', ''),
                        })

            # Отправляем через API
            from messaging.services.bot_api_client import bot_api_client
            result = bot_api_client.send_message(
                user_id=int(user.max_id),
                text=message_text,
                format='html',
                buttons=buttons,
            )

            if result.get('success'):
                step_run.sent_at = django_tz.now()
                step_run.save(update_fields=['sent_at'])

                Log.objects.create(
                    run=self.run,
                    event_type=Log.EVENT_STEP_SENT,
                    payload_json={
                        'user_id': user_id,
                        'step_id': step.id,
                        'step_order': step.step_order,
                        'message': message_text[:200],
                    },
                )

                logger.info(f'Сообщение отправлено пользователю {user_id} (max_id={user.max_id})')
            else:
                error_msg = result.get('error', 'Unknown error')
                step_run.status = StepRun.STATUS_FAILED
                step_run.error_message = error_msg
                step_run.save()
                logger.error(f'Ошибка отправки сообщения пользователю {user_id}: {error_msg}')
        except Exception as e:
            error_msg = str(e)
            step_run.status = StepRun.STATUS_FAILED
            step_run.error_message = error_msg
            step_run.save()
            logger.error(f'Ошибка отправки сообщения пользователю {user_id}: {error_msg}')

    def _resolve_mailing_list(self, step: Step) -> list:
        """
        Резолвим mailing_list_json в сотрудников.
        Формат: [{"type": "role", "name": "...", "scope": "..."}, ...]
        """
        mailing = step.mailing_list_json
        if not isinstance(mailing, list):
            mailing = []

        users = set()

        for item in mailing:
            if not isinstance(item, dict):
                continue

            item_type = item.get('type', '')

            if item_type == 'role':
                # По pk роли
                role_id = item.get('value', '')
                role_id = self._substitute_vars(role_id)
                role = Role.objects.filter(pk=role_id).first()
                if role:
                    # Получаем сотрудников с этой ролью
                    from scenarios.models import EmployeeRole
                    er_qs = EmployeeRole.objects.filter(role=role)

                    for er in er_qs.select_related('employee'):
                        if er.employee.is_active:
                            users.add(er.employee)

            elif item_type == 'user':
                # По pk сотрудника
                user_id = item.get('value', '')
                user_id = self._substitute_vars(user_id)
                user = User.objects.filter(pk=user_id).first()
                if user and user.is_active:
                    users.add(user)

            elif item_type == 'department':
                # По pk подразделения
                dept_id = item.get('value', '')
                dept_id = self._substitute_vars(dept_id)
                dept = Department.objects.filter(pk=dept_id).first()
                if dept:
                    for user in User.objects.filter(department=dept, is_active=True):
                        users.add(user)

        return list(users)

    def _exclude_list(self, users: list, step: Step) -> list:
        """Вычитаем исключённых сотрудников."""
        exclusion = step.exclusion_list_json
        if not isinstance(exclusion, list):
            return users

        excluded = set()
        for item in exclusion:
            if isinstance(item, dict):
                item_type = item.get('type', '')
                value = item.get('value', '')
                value = self._substitute_vars(value)

                if item_type == 'user':
                    user = User.objects.filter(pk=value).first()
                    if user:
                        excluded.add(user)
                elif item_type == 'role':
                    from scenarios.models import Role, EmployeeRole
                    role = Role.objects.filter(pk=value).first()
                    if role:
                        for er in EmployeeRole.objects.filter(role=role):
                            excluded.add(er.employee)
                elif item_type == 'department':
                    from accounts.models import Department
                    dept = Department.objects.filter(pk=value).first()
                    if dept:
                        for u in User.objects.filter(department=dept, is_active=True):
                            excluded.add(u)
                elif item_type == 'mail_group':
                    from scenarios.models import ScenarioMailGroup
                    group = ScenarioMailGroup.objects.filter(pk=value).first()
                    if group:
                        for u in group.users.all():
                            excluded.add(u)
                        for dept in group.departments.all():
                            for u in User.objects.filter(department=dept, is_active=True):
                                excluded.add(u)

        return [u for u in users if u not in excluded]

    def _calc_deadline(self, step: Step):
        """Вычисляем время дедлайна."""
        if step.deadline_min > 0:
            return django_tz.now() + timedelta(minutes=step.deadline_min)
        return None

    # ========================================================================
    # Обработка ответа
    # ========================================================================

    def process_answer(
        self,
        user_id: int,
        message_text: str,
        button_result_code: str = None,
        step_run: 'StepRun' = None,
    ) -> dict:
        """
        Обработка ответа пользователя.

        Args:
            user_id: ID пользователя
            message_text: Текст сообщения (для текстовых ответов)
            button_result_code: Код нажатой кнопки (для кнопок)
            step_run: Готовый step_run (если уже найден)

        Returns:
            dict с результатом обработки
        """
        logger.info(f'process_answer: user_id={user_id}, button_code={button_result_code}, text={message_text[:50]}')
        # Находим активный step_run пользователя
        if step_run is None:
            step_run = StepRun.objects.filter(
                run=self.run,
                recipient_id=user_id,
                status=StepRun.STATUS_SENT,
            ).order_by('step__step_order').first()

        if not step_run:
            return {'success': False, 'error': 'Нет активного шага'}

        step = step_run.step
        message_json = step.message_json
        logger.info(f'process_answer: step_id={step.id}, step_order={step.step_order}, message_json={message_json}')

        # Валидируем ответ
        validated_answer = self._validate_answer(message_json, message_text, button_result_code)
        if not validated_answer:
            return {'success': False, 'error': 'Невалидный ответ'}

        # Сохраняем ответ
        with transaction.atomic():
            answer = Answer.objects.create(
                run=self.run,
                step_run=step_run,
                employee_id=user_id,
                answer_json=validated_answer,
            )

            # Обновляем step_run
            step_run.status = StepRun.STATUS_ANSWERED
            step_run.result_code = validated_answer.get('result_code', '')
            step_run.save()

            # Лог
            Log.objects.create(
                run=self.run,
                event_type=Log.EVENT_ANSWER_RECEIVED,
                payload_json={
                    'user_id': user_id,
                    'step_id': step.id,
                    'step_order': step.step_order,
                    'prev_result_code': step.prev_result_code,
                    'answer': validated_answer,
                },
            )

            # Записываем в db_values
            self._write_db_values(step, validated_answer, user_id)

            # Вычисляем агрегаты шага
            aggregates = self._compute_step_aggregates(step)

        # Ищем следующий шаг (вне транзакции)
        next_step = self._find_next_step(step, validated_answer.get('result_code', ''))
        logger.info(f'process_answer: next_step_id={next_step.id if next_step else None}')

        result = {
            'success': True,
            'step_completed': next_step is None,
            'next_step_id': next_step.id if next_step else None,
            'scenario_id': self.run.scenario_id,
            'aggregates': aggregates,
        }

        if next_step:
            # Отправляем следующий шаг
            logger.info(f'process_answer: sending next step {next_step.id} to user {user_id}')
            self._send_next_step(next_step, user_id)
            result['next_message'] = self._substitute_vars(next_step.message_text, aggregates)
            result['next_buttons'] = next_step.message_json.get('options', [])
        else:
            logger.info(f'process_answer: no next step found for user {user_id}')

        return result

    def _validate_answer(self, message_json, text, button_code):
        """Валидирует ответ по message_json."""
        answer_type = message_json.get('type', '')

        if answer_type == 'buttons':
            # Проверка кнопки
            options = message_json.get('options', [])
            logger.debug(f'Validate buttons: button_code={button_code}, options={[(o.get("text"), o.get("result_code")) for o in options]}')
            for opt in options:
                if opt.get('result_code') == button_code:
                    return {
                        'result_code': button_code,
                        'button_text': opt.get('text', ''),
                    }
            return None

        elif answer_type == 'number':
            # Проверка числа
            logger.info(f'_validate_answer number: text={text}, message_json={message_json}')
            try:
                value = int(text.strip())
            except (ValueError, AttributeError):
                logger.info(f'_validate_answer number: failed to convert text to int')
                return None

            validation = message_json.get('validation', {})
            min_val = validation.get('min', float('-inf'))
            max_val = validation.get('max', float('inf'))

            if value < min_val or value > max_val:
                logger.info(f'_validate_answer number: value {value} out of range [{min_val}, {max_val}]')
                return None

            logger.info(f'_validate_answer number: valid, value={value}')
            return {
                'result_code': message_json.get('result_code', 'NUMBER'),
                'value': value,
            }

        elif answer_type == 'text_pattern':
            # Парсинг текста по паттерну
            pattern = message_json.get('pattern', '')
            fields = message_json.get('fields', [])

            match = re.match(pattern, text.strip())
            if not match:
                return None

            result = {
                'result_code': message_json.get('result_code', 'TEXT'),
                'raw': text.strip(),
            }
            for i, field in enumerate(fields):
                result[field] = match.group(i + 1)

            return result

        elif answer_type == 'buttons_with_number':
            # Комбинированный: кнопка + число
            options = message_json.get('options', [])
            for opt in options:
                if opt.get('result_code') == button_code:
                    result = {
                        'result_code': button_code,
                        'button_text': opt.get('text', ''),
                    }
                    # Если нужно число
                    ask_number = opt.get('ask_number')
                    if ask_number:
                        try:
                            result[ask_number.get('result_code', 'NUMBER')] = int(text.strip())
                        except (ValueError, AttributeError):
                            return None
                    return result
            return None

        return None

    def _write_db_values(self, step: Step, answer: dict, user_id: int):
        """Записывает ответы в db_values по db_write_json."""
        db_write = step.db_write_json
        if not db_write or not isinstance(db_write, dict):
            return

        for key, template in db_write.items():
            value = self._substitute_template(template, answer, user_id)
            DbValue.objects.update_or_create(
                run=self.run,
                employee_id=user_id,
                key=key,
                defaults={'value': str(value)},
            )

    def _compute_step_aggregates(self, step: Step) -> dict:
        """Вычисляет агрегаты по ответам шага."""
        step_runs = StepRun.objects.filter(
            run=self.run,
            step=step,
            status=StepRun.STATUS_ANSWERED,
        )

        aggregates = {
            'responders': step_runs.count(),
            'expected': step_runs.model.objects.filter(
                run=self.run,
                step=step,
            ).count(),
            'missing': 0,
        }

        # Сумма для числовых ответов
        if step.message_json.get('type') == 'number':
            result_code = step.message_json.get('result_code', '')
            values = []
            for sr in step_runs:
                answer = Answer.objects.filter(step_run=sr).first()
                if answer and result_code in answer.answer_json:
                    values.append(answer.answer_json[result_code])
            aggregates['sum'] = sum(values)

        # Для text_pattern — список по палатам
        elif step.message_json.get('type') == 'text_pattern':
            result_code = step.message_json.get('result_code', '')
            ward_data = []
            for sr in step_runs:
                answer = Answer.objects.filter(step_run=sr).first()
                if answer and result_code in answer.answer_json:
                    ward_data.append(answer.answer_json[result_code])
            aggregates['wards'] = ward_data

        aggregates['missing'] = aggregates['expected'] - aggregates['responders']
        return aggregates

    def _find_next_step(self, current_step: Step, result_code: str) -> Step:
        """Находит следующий шаг в ветке по prev_result_code."""
        logger.info(f'_find_next_step: step_id={current_step.id}, result_code={result_code}, branch_id={current_step.branch_id}')
        candidates = current_step.branch.steps.filter(
            prev_result_code=result_code,
        ).order_by('step_order')
        logger.info(f'_find_next_step: found {candidates.count()} candidates')
        for c in candidates:
            logger.info(f'  candidate: step_id={c.id}, step_order={c.step_order}, prev_result_code={c.prev_result_code!r}')
        return candidates.first()

    def _send_next_step(self, step: Step, user_id: int):
        """Отправляет следующий шаг пользователю."""
        logger.info(f'_send_next_step: step_id={step.id}, step_order={step.step_order}, user_id={user_id}')
        step_run, created = StepRun.objects.get_or_create(
            run=self.run,
            step=step,
            recipient_id=user_id,
            defaults={
                'status': StepRun.STATUS_SENT,
                'deadline_at': self._calc_deadline(step),
            },
        )
        logger.info(f'_send_next_step: step_run_id={step_run.pk}, created={created}, status={step_run.status}')

        # Обновляем текущий запуск пользователя
        from scenarios.models import UserCurrentRun
        UserCurrentRun.objects.update_or_create(
            user_id=user_id,
            defaults={'run': self.run},
        )
        logger.info(f'_send_next_step: updated UserCurrentRun for user {user_id} -> run_id={self.run.id}')

        if not created:
            # Уже есть step_run — обновляем
            step_run.status = StepRun.STATUS_SENT
            step_run.result_code = ''
            step_run.deadline_at = self._calc_deadline(step)
            step_run.save()

        # Отправляем сообщение через MAX API
        from messaging.services.max_api import MAXClient, MAXAPIError
        from accounts.models import User as AccountUser

        user = AccountUser.objects.get(pk=user_id)
        if not user.max_id:
            logger.warning(f'У пользователя {user_id} нет max_id')
            return

        try:
            message_text = self._substitute_vars(step.message_text)
            logger.info(f'_send_next_step: sending message to user {user_id} (max_id={user.max_id}): {message_text[:100]}')

            # Формируем кнопки из message_json
            buttons = None
            message_json = step.message_json
            if isinstance(message_json, dict):
                msg_type = message_json.get('type', '')
                if msg_type in ('buttons', 'buttons_with_number'):
                    options = message_json.get('options', [])
                    buttons = []
                    for opt in options:
                        buttons.append({
                            'type': 'callback',
                            'text': opt.get('text', ''),
                            'payload': opt.get('result_code', ''),
                        })
                    logger.info(f'_send_next_step: buttons={buttons}')

            # Отправляем через API
            from messaging.services.bot_api_client import bot_api_client
            result = bot_api_client.send_message(
                user_id=int(user.max_id),
                text=message_text,
                format='html',
                buttons=buttons,
            )
            logger.info(f'_send_next_step: send result={result}')

            if result.get('success'):
                step_run.sent_at = django_tz.now()
                step_run.save()

                Log.objects.create(
                    run=self.run,
                    event_type=Log.EVENT_STEP_SENT,
                    payload_json={
                        'user_id': user_id,
                        'step_id': step.id,
                        'step_order': step.step_order,
                    },
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                step_run.status = StepRun.STATUS_FAILED
                step_run.error_message = error_msg
                step_run.save()
                logger.error(f'Ошибка отправки шага {step.id} пользователю {user_id}: {error_msg}')
        except Exception as e:
            error_msg = str(e)
            step_run.status = StepRun.STATUS_FAILED
            step_run.error_message = error_msg
            step_run.save()
            logger.error(f'Ошибка отправки шага {step.id} пользователю {user_id}: {error_msg}')

    # ========================================================================
    # Переменные
    # ========================================================================

    def _substitute_vars(self, text, aggregates: dict = None):
        """Подставляет переменные в текст."""
        if text is None:
            return text
        if not isinstance(text, str):
            return text
        if '{' not in text:
            return text

        result = text

        # Переменные контекста запуска
        for key, value in self.context.items():
            result = result.replace(f'{{{key}}}', str(value))

        # Переменные пользователя
        result = result.replace('{now}', datetime.now().strftime('%d.%m.%Y %H:%M'))

        return result

    def _substitute_template(self, template, answer: dict, user_id: int) -> str:
        """Подставляет значения в шаблон db_write_json."""
        if isinstance(template, str):
            result = template

            # {user.поле}
            user = User.objects.get(pk=user_id)
            result = result.replace('{user.name}', user.get_full_name())
            if user.department:
                result = result.replace('{user.department}', user.department.name)

            # {answer.CODE}
            for key, value in answer.items():
                if key not in ('result_code', 'button_text', 'raw'):
                    result = result.replace(f'{{answer.{key}}}', str(value))

            return result

        return template  # Для не-строк возвращаем как есть
