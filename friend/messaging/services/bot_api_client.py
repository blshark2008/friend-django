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

    def send_message(self, user_id=None, chat_id=None, text='', format='html', buttons=None):
        """
        Отправить сообщение пользователю через MAX API напрямую.

        Args:
            user_id: ID пользователя в MAX (для каналов)
            chat_id: ID чата/диалога (для диалогов и групповых чатов)
            text: Текст сообщения
            format: Разметка текста ('html', 'markdown')
            buttons: Список кнопок [{'type': 'callback', 'text': '...', 'payload': '...'}]

        Returns:
            dict с результатом
        """
        from messaging.services.max_api import MAXClient, MAXAPIError

        if not user_id and not chat_id:
            logger.error('Must specify user_id or chat_id')
            return {'success': False, 'error': 'Missing user_id or chat_id'}

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
                user_id=int(user_id) if user_id else None,
                chat_id=int(chat_id) if chat_id else None,
                text=text,
                format=format,
                buttons=max_buttons,
            )
            dest = chat_id or user_id
            logger.info(f'Message sent to {dest} via MAX API')
            return {'success': True}
        except MAXAPIError as e:
            dest = chat_id or user_id
            logger.error(f'MAX API error sending to {dest}: {e}')
            return {'success': False, 'error': str(e)}
        except Exception as e:
            dest = chat_id or user_id
            logger.error(f'Error sending message to {dest}: {e}')
            return {'success': False, 'error': str(e)}

# Глобальный клиент
bot_api_client = BotAPIClient()
