from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from siem.models import SecurityEvent, InventorySnapshot


class Command(BaseCommand):
    help = 'Очистка старых событий и снимков (retention policy)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=90,
            help='Хранить события за последние N дней (по умолч. 90)',
        )
        parser.add_argument(
            '--keep-critical', action='store_true',
            help='Не удалять критические события даже старше N дней',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Показать что будет удалено, но не удалять',
        )

    def handle(self, *args, **options):
        days = options['days']
        keep_critical = options['keep_critical']
        dry_run = options['dry_run']

        cutoff = timezone.now() - timezone.timedelta(days=days)

        # События
        events_qs = SecurityEvent.objects.filter(occurred_at__lt=cutoff)

        if keep_critical:
            # Удаляем только не-критические
            to_delete = events_qs.filter(severity__in=['info', 'warning', 'error'])
            total_qs = events_qs
        else:
            to_delete = events_qs
            total_qs = events_qs

        events_count = total_qs.count()
        events_to_delete = to_delete.count()

        # Снимки
        snaps_count = InventorySnapshot.objects.filter(
            collected_at__lt=cutoff
        ).count()

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SIEM RETENTION CLEANUP'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'  Порог: {days} дней (до {cutoff:%Y-%m-%d})')
        self.stdout.write(f'')
        self.stdout.write(f'  События всего старше:    {events_count}')
        self.stdout.write(f'  События к удалению:      {events_to_delete}')
        self.stdout.write(f'  Снимки к удалению:       {snaps_count}')
        self.stdout.write(self.style.SUCCESS('=' * 60))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — ничего не удалено'))
            return

        if events_to_delete > 0:
            deleted, _ = to_delete.delete()
            self.stdout.write(
                self.style.SUCCESS(f'  Удалено событий:        {deleted}')
            )

        if snaps_count > 0:
            deleted_snaps, _ = InventorySnapshot.objects.filter(
                collected_at__lt=cutoff
            ).delete()
            self.stdout.write(
                self.style.SUCCESS(f'  Удалено снимков:        {deleted_snaps}')
            )

        self.stdout.write(self.style.SUCCESS('Очистка завершена.'))
