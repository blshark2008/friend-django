# Skillspace Integration - System Overview

## Настройка

### 1. API Configuration (settings.py)
```python
SKILLSPACE_API_KEY = '3e8fcf56-7ed2-3c73-8626-4684263b44c0'
SKILLSPACE_SCHOOL_DOMAIN = 'kemcardio.skillspace.ru'
SKILLSPACE_BASE_URL = 'https://kemcardio.skillspace.ru/api/open/v1'
SKILLSPACE_WEBHOOK_BASE_URL = 'https://84.54.59.213'
```

### 2. Webhook Setup in Skillspace

1. Войдите в Skillspace: https://kemcardio.skillspace.ru
2. Перейдите в: Настройки → Webhooks
3. Добавьте URL:
   ```
   https://84.54.59.213/training/types/<type_id>/trainings/<training_id>/sync-webhook/
   ```
4. Подпишитесь на события:
   - `student_completed` - ученик прошёл курс
   - `student_test_passed` - ученик сдал тест
   - `student_failed` - ученик не сдал тест
   - `student_started` - ученик начал обучение

## Функционал

### Назначение обучения сотрудникам

1. **Создание обучения:**
   - Тип обучения → Создать обучение
   - Выберите сотрудников
   - Укажите даты начала/окончания
   - Сохраните

2. **Синхронизация с Skillspace:**
   - Откройте обучение
   - Нажмите "Синхронизировать"
   - Система автоматически:
     - Запишет всех не начатых сотрудников на курс
     - Обновит статусы на "В процессе"
     - Отправит приглашения на email

3. **Контроль прогресса:**
   - Статистика по статусам:
     - Не начато
     - В процессе
     - Прошли
     - Не пройдено
   - Процент прохождения
   - Детальный список сотрудников с баллами

### API Endpoints

#### POST /training/trainings/<pk>/sync/
Массовая запись сотрудников на курс
- Записывает всех `not_started` сотрудников
- Обновляет статус на `in_progress`
- Возвращает редирект на страницу обучения

#### POST /training/trainings/<pk>/add-user/
Добавить пользователя в обучение (AJAX)
- Parameters: `user_id`
- Returns: JSON with success/user_name

#### POST /training/trainings/<pk>/remove-user/<user_id>/
Удалить пользователя из обучения (AJAX)
- Returns: JSON with status

#### POST /training/trainings/<pk>/check-progress/
Проверить прогресс обучения (AJAX)
- Returns: JSON с статистикой

#### POST /training/trainings/<pk>/invite-link/
Получить ссылку для приглашения
- Returns: JSON с invite_url

#### POST /training/trainings/<pk>/sync-webhook/
Webhook endpoint для Skillspace
- Принимает события от Skillspace
- Автоматически обновляет статусы enrollments

### Management Commands

```bash
# Показать webhook URL
python manage.py show_webhook_url

# Синхронизировать все обучения
python manage.py sync_trainings

# Синхронизировать конкретное обучение
python manage.py sync_trainings --training-id=123
```

## API Documentation (Skillspace Open API)

### Пригласить ученика на курс

**Endpoint:** `POST/GET /api/open/v1/course/student-invite`

**Parameters:**
- `token` - API key (required)
- `email` - Email ученика (required)
- `courses[ID]` - ID курса (required)
- `name` - Имя ученика
- `disableNotification` - Не отправлять email

**Response (200):**
```json
{
  "password": "...",
  "passwordSetupLink": "https://..."
}
```
- Пустой ответ `{}` - ученик уже записан

**Errors:**
- `400 INVALID_EMAIL` - неверный email
- `400 INVITE_USER_CANT_DETECT_COURSE` - не указан курс
- `404 COURSE_NOT_FOUND` - курс не найден
- `403 FLOW_FROM_ANOTHER_COURSE` - группа из другого курса

## Database Models

### TrainingType
- `name` - Название типа обучения
- `skillspace_course_id` - ID курса на Skillspace
- `is_active` - Активен ли тип

### Training
- `training_type` - FK to TrainingType
- `title` - Название обучения
- `status` - pending/active/completed/archived
- `start_date` / `end_date` - Период проведения
- `last_sync_at` - Последняя синхронизация
- `is_active` - Активно ли

### TrainingEnrollment
- `training` - FK to Training
- `user` - FK to User
- `status` - not_started/in_progress/completed/failed
- `score` - Балл за тест
- `completed_at` - Дата прохождения
- `skillspace_student_id` - ID студента на Skillspace

## Workflow

1. **Создание:** Admin создаёт TrainingType с skillspace_course_id
2. **Назначение:** Admin создаёт Training, выбирает сотрудников
3. **Синхронизация:** Нажимает "Синхронизировать"
   - Система вызывает Skillspace API для записи студентов
   - Статусы обновляются на "in_progress"
4. **Отслеживание:**
   - Skillspace отправляет webhook при завершении
   - Статусы обновляются автоматически
   - Admin видит прогресс в реальном времени
5. **Отчётность:**
   - Статистика по подразделениям
   - Статистика по типам обучения
   - Список не прошедших

## Troubleshooting

### Students not enrolled
- Check `skillspace_course_id` is set in TrainingType
- Verify user has corporate_email or personal_email
- Check Skillspace API key in settings

### Webhook not working
- Verify webhook URL is accessible from internet
- Check Skillspace school settings → Webhooks
- Monitor Django logs for webhook events

### Progress not updating
- Check webhook events are being received
- Verify email addresses match between User and Skillspace
- Check Skillspace API response format
