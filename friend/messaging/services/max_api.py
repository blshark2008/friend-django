"""
MAX API Client — клиент для взаимодействия с API мессенджера MAX.

Документация: https://dev.max.ru/docs-api/
Base URL: https://platform-api2.max.ru
"""

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MAXAPIError(Exception):
    """Ошибка API MAX."""
    pass


class MAXClient:
    """Клиент для MAX API."""

    def __init__(self, token=None, base_url=None):
        self.token = token or getattr(settings, 'MAX_BOT_TOKEN', '')
        self.base_url = base_url or getattr(settings, 'MAX_API_BASE_URL', 'https://platform-api2.max.ru')
        if not self.token:
            raise MAXAPIError('MAX_BOT_TOKEN не настроен в settings.py')

    def _headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': self.token,
        }

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """GET запрос к API."""
        url = f'{self.base_url}{endpoint}'
        try:
            response = requests.get(url, headers=self._headers(), params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'MAX API GET error on {endpoint}: {e}')
            raise MAXAPIError(f'GET {endpoint}: {e}')

    def _post(self, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """POST запрос к API."""
        url = f'{self.base_url}{endpoint}'
        try:
            response = requests.post(url, headers=self._headers(), json=data, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'MAX API POST error on {endpoint}: {e}')
            raise MAXAPIError(f'POST {endpoint}: {e}')

    def get_me(self) -> dict:
        """Получить информацию о боте."""
        return self._get('/me')

    def send_message(self, user_id: int = None, chat_id: int = None,
                     text: str = None, format: str = None,
                     disable_link_preview: bool = None,
                     buttons: list = None) -> dict:
        """
        Отправить сообщение в диалог, групповой чат или канал.

        Args:
            user_id: ID пользователя (для диалога)
            chat_id: ID чата или канала
            text: Текст сообщения (до 4000 символов)
            format: Разметка текста — 'markdown' или 'html'
            disable_link_preview: Не генерировать превью ссылок
            buttons: Список кнопок для inline_keyboard

        Returns:
            dict с объектом Message
        """
        if not user_id and not chat_id:
            raise MAXAPIError('Необходимо указать user_id или chat_id')
        if not text:
            raise MAXAPIError('Необходимо указать текст сообщения')

        params = {}
        if user_id:
            params['user_id'] = user_id
        if chat_id:
            params['chat_id'] = chat_id
        if disable_link_preview is not None:
            params['disable_link_preview'] = disable_link_preview

        payload = {'text': text}
        if format:
            payload['format'] = format
        
        # Добавляем кнопки если есть
        if buttons:
            payload['attachments'] = [{
                'type': 'inline_keyboard',
                'payload': {
                    'buttons': [buttons]  # MAX требует двумерный массив
                }
            }]

        return self._post('/messages', data=payload, params=params)

    def get_updates(self, limit: int = 100, timeout: int = 30,
                    marker: int = None, types: list = None) -> dict:
        """
        Получить обновления через Long Polling.

        Args:
            limit: Максимум обновлений (1-1000)
            timeout: Таймаут в секундах (0-90)
            marker: Marker предыдущего обновления (или None для последнего)
            types: Список типов событий

        Returns:
            dict с ключом 'updates' — список Update объектов
        """
        params = {
            'limit': limit,
            'timeout': timeout,
        }
        if marker is not None:
            params['marker'] = marker
        if types:
            params['types'] = ','.join(types)

        return self._get('/updates', params=params)

    def subscribe_webhook(self, url: str, update_types: list = None,
                          secret: str = None) -> dict:
        """
        Подписаться на webhook-уведомления.

        Args:
            url: HTTPS URL webhook-endpoint (порт 443)
            update_types: Список типов событий
            secret: Секретный ключ для проверки подлинности

        Returns:
            dict с 'success' и 'message'
        """
        payload = {'url': url}
        if update_types:
            payload['update_types'] = update_types
        if secret:
            payload['secret'] = secret

        return self._post('/subscriptions', data=payload)

    def unsubscribe_webhook(self) -> dict:
        """Отписаться от webhook-уведомлений."""
        # DELETE /subscriptions — используем requests напрямую
        url = f'{self.base_url}/subscriptions'
        try:
            response = requests.delete(url, headers=self._headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'MAX API DELETE /subscriptions error: {e}')
            raise MAXAPIError(f'DELETE /subscriptions: {e}')

    def answer_callback(self, chat_id: int, message_id: int,
                        callback_id: str, text: str = None) -> dict:
        """Ответ на callback от кнопки."""
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'callback_id': callback_id,
        }
        if text:
            payload['text'] = text

        return self._post('/answers', data=payload)
