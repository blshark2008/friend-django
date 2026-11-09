"""
MAX Bot API Client — клиент для отправки сообщений через MAX API.

Используется Django для отправки сообщений и управления сценариями.
Отправляет напрямую через MAX API (без relay-сервера).
"""

import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BotAPIClient:
    """Клиент для MAX Bot API — отправляет напрямую."""

    def send_message(self, user_id, text, format='html', buttons=None):
        """
        Отправить сообщение пользователю через MAX API напрямую.

        Args:
            user_id: ID пользователя в MAX
            text: Текст сообщения
            format: Разметка текста ('html', 'markdown')
            buttons: Список кнопок [{'type': 'callback', 'text': '...', 'payload': '...'}]

        Returns:
            dict с результатом
        """
        from messaging.services.max_api import MAXClient, MAXAPIError

        try:
            client = MAXClient()
            
            # Форматируем кнопки для MAX API
            max_buttons = None
            if buttons:
                max_buttons = []
                for btn in buttons:
                    max_buttons.append({
                        'type': btn.get('type', 'callback'),
                        'text': btn.get('text', ''),
                        'payload': btn.get('payload', ''),
                    })
            
            client.send_message(
                user_id=int(user_id),
                text=text,
                format=format,
                buttons=max_buttons,
            )
            logger.info(f'Message sent to user {user_id} via MAX API')
            return {'success': True}
        except MAXAPIError as e:
            logger.error(f'MAX API error sending to user {user_id}: {e}')
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f'Error sending message to user {user_id}: {e}')
            return {'success': False, 'error': str(e)}

# Глобальный клиент
bot_api_client = BotAPIClient()
