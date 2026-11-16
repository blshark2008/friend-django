"""
Management command to import grants for both internal and external users from CSV file.
CSV format: DisplayName, SamAccountName, EmailAddress, SecurityGroups
Security groups are separated by ":"
Matching is done by FULL name (Last Name + First Name + Patronymic) for both user types.
"""
import csv
import io
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date
from access.models import AccessGrant, AccessGroup, ExternalUser
from accounts.models import User


def parse_csv_groups(groups_str):
    """Parse groups string separated by ':'."""
    if not groups_str or not groups_str.strip():
        return []
    
    groups = []
    for g in groups_str.split(':'):
        g = g.strip()
        if g:
            groups.append(g)
    return groups


def normalize_name(name):
    """Normalize name for comparison - lowercase, strip extra spaces."""
    if not name:
        return ''
    return ' '.join(name.lower().split())


def find_user_by_full_name(display_name):
    """
    Find internal user by FULL name match (last + first + patronymic).
    Returns User object or None.
    """
    if not display_name:
        return None
    
    parts = display_name.split()
    if len(parts) < 2:
        return None
    
    last_name = parts[0].strip()
    first_name = parts[1].strip()
    patronymic = ' '.join(parts[2:]).strip() if len(parts) > 2 else ''
    
    # Build query - must match last name and first name exactly
    qs = User.objects.filter(
        last_name__iexact=last_name,
        first_name__iexact=first_name,
        is_active=True,
    )
    
    # If patronymic exists, must match it too
    if patronymic:
        qs = qs.filter(patronymic__iexact=patronymic)
    
    users = list(qs)
    
    # If multiple matches, try exact match
    if len(users) == 1:
        return users[0]
    elif len(users) > 1:
        # Try to find exact match by comparing full normalized names
        normalized_display = normalize_name(display_name)
        for user in users:
            user_full = f"{user.last_name} {user.first_name} {user.patronymic}".strip()
            if normalize_name(user_full) == normalized_display:
                return user
        # If no exact match, return first
        return users[0]
    
    return None


def find_external_user_by_full_name(display_name):
    """
    Find external user by FULL name match (last + first + patronymic).
    Returns ExternalUser object or None.
    """
    if not display_name:
        return None
    
    parts = display_name.split()
    if len(parts) < 2:
        return None
    
    last_name = parts[0].strip()
    first_name = parts[1].strip()
    patronymic = ' '.join(parts[2:]).strip() if len(parts) > 2 else ''
    
    # Build query - must match last name and first name exactly
    qs = ExternalUser.objects.filter(
        full_name__icontains=last_name,
        is_active=True,
    )
    
    # Filter by first name
    qs = qs.filter(full_name__icontains=first_name)
    
    # If patronymic exists, must match it too
    if patronymic:
        qs = qs.filter(full_name__icontains=patronymic)
    
    users = list(qs)
    
    if len(users) == 1:
        return users[0]
    elif len(users) > 1:
        # Try to find exact match by comparing full normalized names
        normalized_display = normalize_name(display_name)
        for user in users:
            if normalize_name(user.full_name) == normalized_display:
                return user
        # If no exact match, return first
        return users[0]
    
    return None


class Command(BaseCommand):
    help = 'Import grants for both internal and external users from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')
        parser.add_argument('--dry-run', action='store_true', help='Preview changes without saving')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options['dry_run']

        self.stdout.write(f'Parsing CSV file: {csv_file}')

        # Parse CSV
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        reader = csv.reader(io.StringIO(content))
        header = next(reader, None)  # skip header

        if not header:
            self.stdout.write(self.style.ERROR('CSV file is empty or has no header!'))
            return

        self.stdout.write(f'Header: {header}')

        # Collect data
        user_groups = []
        skipped_rows = 0

        for row in reader:
            # Pad row to 4 columns
            while len(row) < 4:
                row.append('')

            display_name = row[0].strip()
            security_groups_str = row[3].strip()

            if not display_name:
                skipped_rows += 1
                continue

            groups = parse_csv_groups(security_groups_str)

            if not groups:
                skipped_rows += 1
                continue

            user_groups.append({
                'display_name': display_name,
                'groups': groups,
            })

        self.stdout.write(f'Parsed {len(user_groups)} users with groups ({skipped_rows} rows skipped)')

        # Find all access groups
        all_groups = dict(AccessGroup.objects.values_list('name', 'pk'))
        self.stdout.write(f'Found {len(all_groups)} access groups in database')

        # Process grants
        created = 0
        updated = 0
        not_found_users = 0
        group_not_found = 0
        errors = []
        matched_internal = 0
        matched_external = 0

        for user_data in user_groups:
            display_name = user_data['display_name']
            groups = user_data['groups']

            # Try to find internal user first
            user = find_user_by_full_name(display_name)
            
            # If not found, try external user
            external_user = None
            if not user:
                external_user = find_external_user_by_full_name(display_name)

            if not user and not external_user:
                not_found_users += 1
                continue

            if user:
                matched_internal += 1
            if external_user:
                matched_external += 1

            # Create grants for each group
            for group_name in groups:
                if group_name not in all_groups:
                    group_not_found += 1
                    continue

                group_id = all_groups[group_name]

                try:
                    # Check if grant already exists (for this specific user and group)
                    existing = AccessGrant.objects.filter(
                        group_id=group_id,
                        grant_type='external' if external_user else 'user',
                        is_active=True,
                    )
                    
                    if external_user:
                        existing = existing.filter(external_user=external_user)
                    else:
                        existing = existing.filter(user=user)
                    
                    existing = existing.first()

                    if existing:
                        # Update existing grant
                        existing.justification = f'Импортировано из {csv_file}'
                        existing.expires_at = date(2027, 11, 13)
                        existing.save()
                        updated += 1
                    else:
                        # Create new grant
                        AccessGrant.objects.create(
                            user=user,
                            external_user=external_user,
                            group_id=group_id,
                            grant_type='external' if external_user else 'user',
                            justification=f'Импортировано из {csv_file}',
                            expires_at=date(2027, 11, 13),
                            is_active=True,
                        )
                        created += 1
                except Exception as e:
                    errors.append(f'Error creating grant for {display_name} -> {group_name}: {e}')

        # Print summary
        self.stdout.write(self.style.SUCCESS(f'\nImport completed!'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created}'))
        self.stdout.write(self.style.SUCCESS(f'  Updated: {updated}'))
        self.stdout.write(f'  Matched (internal users): {matched_internal}')
        self.stdout.write(f'  Matched (external users): {matched_external}')
        self.stdout.write(f'  Not found (users): {not_found_users}')
        self.stdout.write(f'  Not found (groups): {group_not_found}')
        self.stdout.write(f'  Skipped rows: {skipped_rows}')

        if errors:
            self.stdout.write(self.style.ERROR(f'\nErrors ({len(errors)}):'))
            for err in errors[:20]:
                self.stdout.write(f'  - {err}')
            if len(errors) > 20:
                self.stdout.write(f'  ... and {len(errors) - 20} more errors')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - no changes were saved to database'))
