"""
Команда запуска воркера дедлайнов сценариев.

Запуск:
    python manage.py run_deadline_worker --interval=30
"""

import sys
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запуск воркера дедлайнов и эскалаций сценариев'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Интервал проверки в секундах (по умолчанию 30)',
        )

    def handle(self, *args, **options):
        from scenarios.services.deadline_worker import run_deadline_worker

        run_deadline_worker(options['interval'])
