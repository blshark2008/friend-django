#!/usr/bin/env python3
"""
MAX Bot API Server — простой API для взаимодействия с MAX ботом.

Запуск:
    python3 bot_api.py --port 5000

API Endpoints:
    POST /api/send-message
        {"user_id": 15284524, "text": "Привет", "format": "html"}
    
    POST /api/run-scenario
        {"scenario_id": 1, "started_by": 75}
    
    POST /api/process-answer
        {"user_id": 15284524, "button_result_code": "WYG2X6GE"}

Настройка на Django:
    MAX_BOT_API_URL = 'http://84.54.59.213:5000'
"""

import argparse
import json
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


class BotAPIHandler(BaseHTTPRequestHandler):
    """Обработчик API-запросов."""

    # Настройки
    MAX_BOT_TOKEN = ''
    MAX_API_BASE_URL = 'https://platform-api2.max.ru'

    def do_POST(self):
        """Обработка POST-запросов."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        content_type = self.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            self._send_json_response(400, {'error': 'Expected JSON'})
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.warning(f'JSON decode error: {e}')
            self._send_json_response(400, {'error': 'Invalid JSON'})
            return

        logger.info(f'API request: {self.path}')

        if self.path == '/api/send-message':
            self._handle_send_message(data)
        elif self.path == '/api/run-scenario':
            self._handle_run_scenario(data)
        elif self.path == '/api/process-answer':
            self._handle_process_answer(data)
        elif self.path == '/api/health':
            self._send_json_response(200, {
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
            })
        else:
            self._send_json_response(404, {'error': 'Not found'})

    def do_GET(self):
        """Проверка здоровья."""
        if self.path == '/api/health':
            self._send_json_response(200, {
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
            })
        else:
            self._send_json_response(404, {'error': 'Not found'})

    def _handle_send_message(self, data):
        """Отправить сообщение пользователю."""
        user_id = data.get('user_id')
        text = data.get('text')
        format = data.get('format', 'html')
        buttons = data.get('buttons')

        if not user_id or not text:
            self._send_json_response(400, {'error': 'user_id и text обязательны'})
            return

        try:
            import urllib.request
            import urllib.error
            import ssl

            url = f'{self.MAX_API_BASE_URL}/messages?user_id={user_id}'
            payload = {'text': text, 'format': format}
            
            # Формируем кнопки по документации MAX API
            # buttons — это flat-список кнопок, оборачиваем в 2D-массив (один ряд)
            if buttons:
                keyboard = []
                for btn in buttons:
                    keyboard.append({
                        'type': btn.get('type', 'callback'),
                        'text': btn.get('text', ''),
                        'payload': btn.get('payload', ''),
                    })
                # MAX API ожидает 2D-массив: [[кнопка1, кнопка2], [кнопка3]]
                # Все кнопки в одном ряду
                payload['attachments'] = [{
                    'type': 'inline_keyboard',
                    'payload': {
                        'buttons': [keyboard]
                    }
                }]
                logger.info(f'Sending buttons: {json.dumps(payload["attachments"], ensure_ascii=False)}')

            # Отключаем проверку SSL для MAX API
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': self.MAX_BOT_TOKEN,
                },
                method='POST',
            )

            with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                result = json.loads(response.read().decode('utf-8'))
                logger.info(f'Message sent to user {user_id}')
                self._send_json_response(200, {'status': 'ok', 'message': result})

        except Exception as e:
            logger.error(f'Error sending message: {e}')
            self._send_json_response(500, {'error': str(e)})

    def _handle_run_scenario(self, data):
        """Запустить сценарий."""
        scenario_id = data.get('scenario_id')
        started_by = data.get('started_by')

        if not scenario_id or not started_by:
            self._send_json_response(400, {'error': 'scenario_id и started_by обязательны'})
            return

        # TODO: здесь будет логика запуска сценария
        # Пока просто возвращаем заглушку
        self._send_json_response(200, {
            'status': 'ok',
            'message': f'Сценарий {scenario_id} запущен пользователем {started_by}',
        })

    def _handle_process_answer(self, data):
        """Обработать ответ пользователя."""
        user_id = data.get('user_id')
        button_result_code = data.get('button_result_code')
        message_text = data.get('message_text')

        if not user_id:
            self._send_json_response(400, {'error': 'user_id обязателен'})
            return

        # TODO: здесь будет логика обработки ответа
        self._send_json_response(200, {
            'status': 'ok',
            'message': f'Ответ от пользователя {user_id} получен',
        })

    def _send_json_response(self, status_code, data):
        """Отправка JSON-ответа."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        logger.info(f'{self.client_address[0]} - {format % args}')


def main():
    parser = argparse.ArgumentParser(description='MAX Bot API Server')
    parser.add_argument('--port', type=int, default=5000,
                        help='Порт для прослушивания (по умолчанию: 5000)')
    parser.add_argument('--token', default='',
                        help='MAX_BOT_TOKEN')
    parser.add_argument('--base-url', default='https://platform-api2.max.ru',
                        help='MAX API Base URL')
    parser.add_argument('--debug', action='store_true',
                        help='Включить debug-логирование')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    BotAPIHandler.MAX_BOT_TOKEN = args.token
    BotAPIHandler.MAX_API_BASE_URL = args.base_url

    logger.info('=' * 60)
    logger.info('MAX Bot API Server')
    logger.info('=' * 60)
    logger.info(f'Порт: {args.port}')
    logger.info(f'MAX API: {args.base_url}')
    logger.info('=' * 60)
    logger.info('')
    logger.info('API Endpoints:')
    logger.info('  POST /api/send-message    - Отправить сообщение')
    logger.info('  POST /api/run-scenario    - Запустить сценарий')
    logger.info('  POST /api/process-answer  - Обработать ответ')
    logger.info('  GET  /api/health          - Проверка здоровья')
    logger.info('')
    logger.info(f'Сервер запущен на http://0.0.0.0:{args.port}')
    logger.info('=' * 60)

    server = HTTPServer(('0.0.0.0', args.port), BotAPIHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('\nСервер остановлен.')
        server.shutdown()


if __name__ == '__main__':
    main()
