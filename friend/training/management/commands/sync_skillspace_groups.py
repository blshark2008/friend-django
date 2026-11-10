from django.core.management.base import BaseCommand
from training.models import SkillspaceGroup


class Command(BaseCommand):
    help = 'Sync Skillspace groups from API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all', action='store_true',
            help='Sync groups for all courses',
        )

    def handle(self, *args, **options):
        if options['all']:
            count = SkillspaceGroup.sync_all_courses()
            self.stdout.write(self.style.SUCCESS(f'Synced {count} groups for all courses'))
        else:
            self.stdout.write(self.style.WARNING('Use --all to sync all courses'))
