"""
Management command to sync all trainings with Skillspace.

Usage:
    python manage.py sync_trainings
"""

from django.core.management.base import BaseCommand
from training.models import Training
from training.services.skillspace_api import SkillspaceAPIError


class Command(BaseCommand):
    help = 'Sync all active trainings with Skillspace platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--training-id',
            type=int,
            help='Sync only specific training by ID',
        )

    def handle(self, *args, **options):
        training_id = options.get('training_id')

        if training_id:
            trainings = Training.objects.filter(pk=training_id)
        else:
            trainings = Training.objects.filter(is_active=True)

        if not trainings:
            self.stdout.write(self.style.WARNING('No active trainings found.'))
            return

        total = trainings.count()
        self.stdout.write(f'Found {total} training(s) to sync.')

        synced = 0
        errors = 0

        for training in trainings:
            try:
                self.stdout.write(f'Syncing: {training}')
                training.sync_from_skillspace()
                training.sync_to_skillspace()
                training.save(update_fields=['last_sync_at'])
                synced += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Synced: {training}')
                )
            except SkillspaceAPIError as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error: {training} — {e}')
                )
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error: {training} — {e}')
                )

        self.stdout.write(f'\nDone. Synced: {synced}, Errors: {errors}')
