"""
MAX Bot — бот для регистрации пользователей и отправки сообщений.

Логика работы:
1. Пользователь отправляет /register
2. Бот просит ФИО
3. Бот просит табельный номер
4. Проверяет наличие в базе (accounts.User)
5. Предлагает выбрать каналы доставки
6. Регистрирует каналы

Запуск:
    python manage.py runmaxbot

Настройка в settings.py:
    MAX_BOT_TOKEN = '...'
    MAX_API_BASE_URL = 'https://platform-api2.max.ru'
"""

import os
import sys
import logging

import django

# Добавляем проект в путь
project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'friend.settings')
django.setup()

from django.conf import settings
from accounts.models import User

logger = logging.getLogger(__name__)

# ============================================================================
# Структуры ответов бота
# ============================================================================

class BotResponse:
    """Ответ бота с текстом и опциональными кнопками."""
    def __init__(self, text, buttons=None):
        self.text = text
        self.buttons = buttons or []

    def __str__(self):
        return self.text


# ============================================================================
# Состояния бота (state machine)
# ============================================================================

class BotState:
    WAITING_FIO = 'waiting_fio'
    WAITING_TAB_NUMBER = 'waiting_tab_number'
    WAITING_NOTIFY_CHANNELS = 'waiting_notify_channels'
    READY = 'ready'
    ERROR = 'error'


# ============================================================================
# Хранилище временных данных пользователей
# ============================================================================

class UserSessionStore:
    """Хранит временные данные сессий пользователей бота."""

    def __init__(self):
        self._sessions = {}

    def get(self, user_id):
        return self._sessions.get(user_id)

    def set(self, user_id, data):
        self._sessions[user_id] = data

    def update(self, user_id, **kwargs):
        if user_id not in self._sessions:
            self._sessions[user_id] = {}
        self._sessions[user_id].update(kwargs)

    def delete(self, user_id):
        self._sessions.pop(user_id, None)

    def clear(self, user_id):
        self._sessions.pop(user_id, None)


# Глобальное хранилище сессий
session_store = UserSessionStore()


# ============================================================================
# Обработчики команд и состояний (синхронные)
# ============================================================================

def handle_start(user_id, username):
    """Обработка команды /start."""
    session = session_store.get(user_id)
    if session and session.get('state') == BotState.READY:
        user = session.get('user')
        if user:
            channels = []
            if user.notify_max: channels.append('MAX')
            if user.notify_telegram: channels.append('Telegram')
            if user.notify_corporate_email: channels.append('Корп. почта')
            if user.notify_personal_email: channels.append('Лич. почта')

            return BotResponse(
                f"👋 Здравствуйте, {user.get_full_name()}!\n\n"
                f"🔢 Табельный номер: {user.tab_number or '—'}\n"
                f"📂 Подразделение: {user.department.name if user.department else '—'}\n\n"
             )
        else:
            return BotResponse(
                f"👋 Здравствуйте!\n\n"
                f"Вы зарегистрированы в системе оповещения сотрудников.\n\n"
                f"Для повторной регистрации отправьте /register"
            )
    
    # Пользователь не найден в базе — предлагаем регистрацию
    return BotResponse(
        "👋 Добро пожаловать в систему оповещения сотрудников НИИ КПССЗ»!\n\n"
        "Чтобы начать, нажмите кнопку ниже:",
        buttons=[{
            'type': 'callback',
            'text': '📝 Зарегистрироваться',
            'payload': 'register_start'
        }]
    )


def handle_register(user_id, username):
    """Начало регистрации."""
    # Сохраняем chat_id из текущей сессии (если есть)
    existing_session = session_store.get(user_id) or {}
    chat_id = existing_session.get('chat_id')
    
    session_store.clear(user_id)
    session_store.set(user_id, {
        'state': BotState.WAITING_FIO,
        'username': username,
        'chat_id': chat_id,  # Сохраняем chat_id для использования при регистрации
    })
    return (
        "📝 Регистрация в системе сообщений.\n\n"
        "Пожалуйста, отправьте ваше ФИО полностью.\n\n"
        "Пример: Иванов Иван Иванович"
    )


def handle_help():
    """Справка."""
    return (
        "📖 Справка по боту «Друг»\n\n"
        "/start — начать работу с ботом\n"
        "/register — начать регистрацию каналов доставки\n"
        "/status — проверить статус регистрации\n"
        "/help — эта справка\n\n"
        "📌 После регистрации вы будете получать сообщения\n"
        "через выбранные каналы связи."
    )


def handle_status(user_id):
    """Проверка статуса регистрации."""
    session = session_store.get(user_id)
    if not session or session.get('state') == BotState.ERROR:
        return "❌ Вы не зарегистрированы. Отправьте /register для начала регистрации."

    if session.get('state') == BotState.READY:
        user = session.get('user')
        if user:
            channels = []
            if user.notify_max: channels.append('✅ MAX')
            if user.notify_telegram: channels.append('✅ Telegram')
            if user.notify_corporate_email: channels.append('✅ Корп. почта')
            if user.notify_personal_email: channels.append('✅ Лич. почта')

            return (
                f"✅ Вы зарегистрированы!\n\n"
                f"👤 {user.get_full_name()}\n"
                f"🔢 Табельный номер: {user.tab_number or '—'}\n"
                f"📂 Подразделение: {user.department.name if user.department else '—'}\n\n"
             )

    return "⏳ Регистрация в процессе..."


def process_fio(user_id, fio_text):
    """Обработка ФИО."""
    parts = fio_text.strip().split()
    if len(parts) < 2:
        session_store.update(user_id, state=BotState.ERROR)
        return (
            "❌ Ошибка: ФИО должно содержать минимум Фамилию и Имя.\n\n"
            "Пример: Иванов Иван\n\n"
            "Отправьте ФИО снова или /start для возврата в меню."
        )

    last_name, first_name = parts[0], parts[1]
    patronymic = ' '.join(parts[2:]) if len(parts) > 2 else ''

    session_store.update(
        user_id,
        state=BotState.WAITING_TAB_NUMBER,
        last_name=last_name,
        first_name=first_name,
        patronymic=patronymic,
    )
    return f"✅ Спасибо, {last_name} {first_name}!\n\nТеперь отправьте ваш табельный номер."


def process_tab_number(user_id, tab_number):
    """Обработка табельного номера и поиск пользователя."""
    session = session_store.get(user_id)
    last_name = session.get('last_name', '')
    first_name = session.get('first_name', '')
    patronymic = session.get('patronymic', '')

    tab_number_raw = tab_number.strip()

    # Ищем пользователя по табельному номеру с разными вариациями
    user = None
    search_variants = [tab_number_raw]

    # Добавляем варианты без ведущих нулей
    tab_number_no_zeros = tab_number_raw.lstrip('0') or '0'
    if tab_number_no_zeros != tab_number_raw:
        search_variants.append(tab_number_no_zeros)

    # Добавляем варианты с 1-3 ведущими нулями
    for i in range(1, 4):
        padded = '0' * i + tab_number_no_zeros
        if padded != tab_number_raw and padded != tab_number_no_zeros:
            search_variants.append(padded)

    # Пробуем все варианты
    for variant in search_variants:
        user = User.objects.filter(tab_number=variant).first()
        if user:
            break

    if not user:
        # Пробуем найти по ФИО
        user = User.objects.filter(
            last_name__iexact=last_name,
            first_name__iexact=first_name,
            patronymic__iexact=patronymic,
            archive_status=User.STATUS_ACTIVE,
        ).first()

    if not user:
        session_store.update(user_id, state=BotState.ERROR)
        return (
            f"❌ Пользователь с табельным номером «{tab_number}» не найден в базе.\n\n"
            f"Также не найден по ФИО: {last_name} {first_name} {patronymic}\n\n"
            f"Возможные причины:\n"
            f"• Табельный номер указан неверно\n"
            f"• Сотрудник ещё не добавлен в систему\n"
            f"• Сотрудник находится в архиве\n\n"
            f"Обратитесь к администратору системы.\n\n"
            f"Для начала регистрации заново отправьте /register"
        )

    if user.is_fired or user.archive_status == User.STATUS_ARCHIVED:
        session_store.update(user_id, state=BotState.ERROR)
        return (
            f"❌ Сотрудник {user.get_full_name()} находится в архиве.\n"
            f"Регистрация недоступна для уволенных сотрудников.\n\n"
            f"Обратитесь к администратору системы."
        )

    # Пользователь найден — автоматически регистрируем MAX канал
    user.max_id = str(user_id)
    user.notify_max = True
    
    # Сохраняем chat_id из сессии в БД
    session = session_store.get(user_id) or {}
    chat_id = session.get('chat_id')
    if chat_id:
        user.max_chat_id = chat_id
        logger.info(f'Saved chat_id={chat_id} for user {user_id} during registration')
    
    user.save()

    session_store.update(
        user_id,
        state=BotState.READY,
        notify_max=True,
        notify_telegram=False,
        notify_corporate_email=False,
        notify_personal_email=False,
    )

    return (
        f"🎉 Регистрация завершена успешно!\n\n"
        f"👤 {user.get_full_name()}\n"
        f"🔢 Табельный номер: {user.tab_number}\n\n"
        f"Теперь вы будете получать сообщения через MAX.\n"

    )


def process_notify_channels(user_id, channels_text):
    """Обработка выбора каналов."""
    session = session_store.get(user_id)
    user_db_id = session.get('user_id_db')

    if not user_db_id:
        session_store.update(user_id, state=BotState.ERROR)
        return "❌ Ошибка сессии. Начните регистрацию заново: /register"

    # Парсим выбранные каналы
    selected = set()
    for part in channels_text.replace(',', ' ').split():
        part = part.strip()
        if part == '1': selected.add('max')
        elif part == '2': selected.add('telegram')
        elif part == '3': selected.add('corporate_email')
        elif part == '4': selected.add('personal_email')
        elif part.lower() in ('все', 'all', '4'):
            selected = {'max', 'telegram', 'corporate_email', 'personal_email'}

    if not selected:
        return (
            "❌ Не выбрано ни одного канала.\n\n"
            "Отправьте номера каналов через запятую:\n"
            "  1 — MAX\n"
            "  2 — Telegram\n"
            "  3 — Корп. почта\n"
            "  4 — Лич. почта\n\n"
            "Пример: 1, 3"
        )

    # Обновляем настройки пользователя
    user = User.objects.filter(pk=user_db_id).first()
    if not user:
        session_store.update(user_id, state=BotState.ERROR)
        return "❌ Пользователь не найден в системе."

    # Сохраняем MAX user_id для отправки сообщений
    user.max_id = str(user_id)
    user.notify_max = 'max' in selected
    user.notify_telegram = 'telegram' in selected
    user.notify_corporate_email = 'corporate_email' in selected
    user.notify_personal_email = 'personal_email' in selected
    user.save()

    session_store.update(
        user_id,
        state=BotState.READY,
        notify_max=user.notify_max,
        notify_telegram=user.notify_telegram,
        notify_corporate_email=user.notify_corporate_email,
        notify_personal_email=user.notify_personal_email,
        user=user,
    )

    channels_list = []
    if user.notify_max: channels_list.append('MAX')
    if user.notify_telegram: channels_list.append('Telegram')
    if user.notify_corporate_email: channels_list.append('Корп. почта')
    if user.notify_personal_email: channels_list.append('Лич. почта')

    return (
        f"🎉 Регистрация завершена успешно!\n\n"
        f"👤 {user.get_full_name()}\n"
        f"🔢 Табельный номер: {user.tab_number}\n\n"
        f"📌 Активные каналы доставки:\n" +
        '\n'.join(f'  ✅ {ch}' for ch in channels_list) +
        "\n\n"
        f"Теперь вы будете получать сообщения через выбранные каналы.\n"
        f"Для изменения настроек отправьте /register заново."
    )


def handle_message(user_id, message_text):
    """Обработка обычного сообщения (не команды)."""
    session = session_store.get(user_id)

    if not session or session.get('state') == BotState.ERROR:
        return None

    state = session.get('state')

    if state == BotState.WAITING_FIO:
        return process_fio(user_id, message_text.strip())

    elif state == BotState.WAITING_TAB_NUMBER:
        return process_tab_number(user_id, message_text.strip())

    elif state == BotState.WAITING_NOTIFY_CHANNELS:
        return process_notify_channels(user_id, message_text.strip())

    return None


# ============================================================================
# Обработчик команд
# ============================================================================

def handle_command(user_id, command, args=''):
    """Обработка команд бота."""
    # Убираем ведущий слэш
    command = command.lower().strip().lstrip('/')

    if command == 'start':
        return handle_start(user_id, args)
    elif command == 'register':
        return handle_register(user_id, args)
    elif command == 'help':
        return handle_help()
    elif command == 'status':
        return handle_status(user_id)
    elif command == 'callback':
        # Обработка нажатия кнопки callback
        payload = args if args else ''
        return handle_callback(user_id, payload)
    else:
        return handle_message(user_id, command)


def handle_callback(user_id, payload):
    """Обработка нажатия кнопок."""
    if payload == 'register_start':
        return handle_register(user_id, '')
    return None
