from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from siem.models import Host


class Command(BaseCommand):
    help = 'Проверка агентов SIEM: выявление оффлайн-хостов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--offline-hours', type=int, default=24,
            help='Через сколько часов считать хост оффлайн (по умолч. 24)',
        )
        parser.add_argument(
            '--alert', action='store_true',
            help='Вывести предупреждения для оффлайн-хостов',
        )

    def handle(self, *args, **options):
        offline_hours = options['offline_hours']
        alert = options['alert']

        cutoff = timezone.now() - timezone.timedelta(hours=offline_hours)
        offline_hosts = Host.objects.filter(
            last_seen__lt=cutoff
        ).order_by('hostname')

        critical_hosts = Host.objects.filter(
            events__severity='critical',
            events__occurred_at__gte=cutoff
        ).distinct().order_by('hostname')

        total = Host.objects.count()
        offline_count = offline_hosts.count()
        critical_count = critical_hosts.count()

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SIEM AGENT HEALTH CHECK'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'  Всего хостов:          {total}')
        self.stdout.write(f'  Оффлайн (> {offline_hours}ч): {offline_count}')
        self.stdout.write(f'  Крит. события за 24ч:  {critical_count}')
        self.stdout.write(self.style.SUCCESS('=' * 60))

        if offline_hosts.exists():
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('ОФФЛАЙН-ХОСТЫ:'))
            for h in offline_hosts:
                last = h.last_seen.strftime('%Y-%m-%d %H:%M') if h.last_seen else 'никогда'
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠ {h.hostname} — последний контакт: {last}'
                    )
                )

        if critical_hosts.exists() and alert:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('ХОСТЫ С КРИТИЧЕСКИМИ СОБЫТИЯМИ:'))
            for h in critical_hosts:
                crit_count = h.events.filter(
                    severity='critical',
                    occurred_at__gte=cutoff
                ).count()
                self.stdout.write(
                    self.style.ERROR(
                        f'  🔴 {h.hostname} — {crit_count} крит. событий'
                    )
                )

        # Возвращаем код ошибки если есть оффлайн-хосты
        if offline_count > 0 and alert:
            self.stdout.write('')
            self.stdout.write(
                self.style.ERROR(
                    f'НАРУШЕНИЕ: {offline_count} хост(ов) оффлайн!'
                )
            )
            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS(
                f'Все {total} хостов на связи.' if not offline_count
                else f'{total - offline_count}/{total} хостов на связи.'
            )
        )
