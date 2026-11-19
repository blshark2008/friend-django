from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

User = get_user_model()


class Command(BaseCommand):
    help = 'Даёт пользователю все группы и права'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя')

    def handle(self, *args, **options):
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Пользователь "{username}" не найден'))
            return

        # Получаем все группы
        all_groups = Group.objects.all()
        count_groups = all_groups.count()
        user.groups.set(all_groups)
        self.stdout.write(self.style.SUCCESS(f'✓ Назначено {count_groups} групп'))

        # Получаем все права
        all_permissions = Permission.objects.all()
        count_perms = all_permissions.count()
        user.user_permissions.set(all_permissions)
        self.stdout.write(self.style.SUCCESS(f'✓ Назначено {count_perms} прав'))

        # Делаем суперпользователем
        if not user.is_superuser:
            user.is_superuser = True
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.SUCCESS('✓ Пользователь сделан суперпользователем'))

        self.stdout.write(self.style.SUCCESS(f'\nГотово! Пользователь "{username}" теперь имеет все права.'))
