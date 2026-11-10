"""
Management command to display webhook URL for Skillspace.

Usage:
    python manage.py show_webhook_url

This command displays the webhook URL that should be configured
in Skillspace school settings to receive completion events.
"""

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Display webhook URL for Skillspace configuration'

    def handle(self, *args, **options):
        webhook_base = getattr(settings, 'SKILLSPACE_WEBHOOK_BASE_URL', 'https://84.54.59.213')
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SKILLSPACE WEBHOOK CONFIGURATION'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        self.stdout.write('Configure this URL in Skillspace school settings:')
        self.stdout.write('')
        self.stdout.write('  Settings → Webhooks → Add webhook URL')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Webhook URL:'))
        self.stdout.write(self.style.SUCCESS(f'  {webhook_base}/training/webhook/'))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Example:'))
        self.stdout.write(self.style.SUCCESS(f'  {webhook_base}/training/webhook/'))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Events to subscribe to:'))
        self.stdout.write('  - course-begin')
        self.stdout.write('  - course-end-test')
        self.stdout.write('  - test-end')
        self.stdout.write('  - homework-end-test')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
