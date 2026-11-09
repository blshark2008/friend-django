#!/usr/bin/env python3
"""
Webhook Relay для MAX Bot.

Принимает webhook от MAX и пересылает на локальный Django-сервер.
Работает с реальным IP без доменного имени.

Запуск:
    # Прямой HTTPS (самоподписанный сертификат)
    python3 max_webhook_relay.py --local-url http://127.0.0.1:8000 --port 443

    # HTTP (для ngrok или локальной разработки)
    python3 max_webhook_relay.py --local-url http://127.0.0.1:8000 --port 8443
"""

import argparse
import json
import logging
import os
import sys
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


class WebhookRelayHandler(BaseHTTPRequestHandler):
    """Обработчик webhook-запросов от MAX."""

    LOCAL_DJANGO_URL = 'http://127.0.0.1:8000'

    def do_POST(self):
        """Обработка POST-запросов (webhook от MAX)."""
        if self.path != '/max/webhook/':
            logger.warning(f'Неверный путь: {self.path}')
            self._send_json_response(404, {'error': 'Not found'})
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        content_type = self.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            logger.warning(f'Неверный Content-Type: {content_type}')
            self._send_json_response(400, {'error': 'Expected JSON'})
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.warning(f'JSON decode error: {e}')
            self._send_json_response(400, {'error': 'Invalid JSON'})
            return

        logger.info(f'Webhook received: update_type={data.get("update_type")}, '
                    f'path={self.path}, size={len(body)} bytes')

        django_path = '/api/max/webhook/'
        django_url = f'{self.LOCAL_DJANGO_URL}{django_path}'
        
        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                django_url,
                data=body,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                response_body = response.read().decode('utf-8')
                logger.info(f'Django responded: {response.status} - {response_body[:100]}')
                self._send_json_response(200, {'status': 'ok'})

        except urllib.error.HTTPError as e:
            logger.error(f'Django HTTP error: {e.code} - {e.read().decode()[:200]}')
            self._send_json_response(502, {'error': 'Django error'})
        except Exception as e:
            logger.error(f'Forward error: {e}')
            self._send_json_response(502, {'error': str(e)})

    def do_GET(self):
        """Проверка здоровья."""
        self._send_json_response(200, {
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'local_django': self.LOCAL_DJANGO_URL,
            'path': self.path,
        })

    def _send_json_response(self, status_code, data):
        """Отправка JSON-ответа."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        """Кастомное логирование."""
        logger.info(f'{self.client_address[0]} - {format % args}')


def generate_self_signed_cert(cert_path, key_path):
    """Генерирует самоподписанный SSL-сертификат."""
    import subprocess
    
    logger.info(f'Генерация самоподписанного сертификата в {cert_path}...')
    
    subprocess.run([
        'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
        '-keyout', key_path, '-out', cert_path,
        '-days', '365', '-nodes',
        '-subj', '/CN=MAX-Bot/O=Friend-System',
        '-addext', 'subjectAltName=IP:0.0.0.0'
    ], check=True)
    
    logger.info(f'Сертификат создан: {cert_path}')
    logger.info(f'Ключ создан: {key_path}')


def main():
    parser = argparse.ArgumentParser(
        description='MAX Webhook Relay',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--local-url', default='http://127.0.0.1:8000',
                        help='URL локального Django (по умолчанию: http://127.0.0.1:8000)')
    parser.add_argument('--port', type=int, default=8443,
                        help='Порт для прослушивания (по умолчанию: 8443)')
    parser.add_argument('--cert', default=None,
                        help='Путь к SSL-сертификату (для HTTPS)')
    parser.add_argument('--key', default=None,
                        help='Путь к SSL-ключу (для HTTPS)')
    parser.add_argument('--generate-cert', action='store_true',
                        help='Сгенерировать самоподписанный сертификат')
    parser.add_argument('--debug', action='store_true',
                        help='Включить debug-логирование')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    WebhookRelayHandler.LOCAL_DJANGO_URL = args.local_url

    use_https = args.cert and args.key
    if use_https and (not args.cert or not args.key):
        parser.error('--cert и --key должны быть указаны вместе')

    if args.generate_cert:
        generate_self_signed_cert(args.cert or 'cert.pem', args.key or 'key.pem')
        use_https = True
        if not args.cert:
            args.cert = 'cert.pem'
        if not args.key:
            args.key = 'key.pem'

    logger.info('=' * 60)
    logger.info('MAX Webhook Relay')
    logger.info('=' * 60)
    logger.info(f'Локальный Django: {args.local_url}')
    logger.info(f'Порт: {args.port}')
    logger.info(f'HTTPS: {"Да" if use_https else "Нет"}')
    logger.info('=' * 60)
    logger.info('')

    if use_https:
        logger.info('Запуск HTTPS-сервера...')
        
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        
        server = HTTPServer(('0.0.0.0', args.port), WebhookRelayHandler)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        
        logger.info(f'HTTPS сервер запущен на https://0.0.0.0:{args.port}')
    else:
        logger.info('Запуск HTTP-сервера...')
        server = HTTPServer(('0.0.0.0', args.port), WebhookRelayHandler)
        logger.info(f'HTTP сервер запущен на http://0.0.0.0:{args.port}')

    logger.info('')
    logger.info('Ожидание webhook от MAX...')
    logger.info('Нажмите Ctrl+C для остановки')
    logger.info('=' * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('\nСервер остановлен.')
        server.shutdown()


if __name__ == '__main__':
    main()
