from django.core.management.base import BaseCommand
from access.models import AccessGrant


class Command(BaseCommand):
    help = 'Установить дату истечения 12.11.2027 для грантов без срока действия'

    def handle(self, *args, **options):
        grants = AccessGrant.objects.filter(expires_at__isnull=True)
        count = grants.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Все гранты уже имеют срок действия.'))
            return

        self.stdout.write(f'Найдено {count} грантов без срока действия...')

        from django.utils import timezone
        from datetime import date

        new_date = date(2027, 11, 12)
        grants.update(expires_at=new_date)

        self.stdout.write(
            self.style.SUCCESS(f'Успешно обновлено {count} грантов. Срок действия: {new_date.strftime("%d.%m.%Y")}')
        )
