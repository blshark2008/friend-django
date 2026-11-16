"""
Management command to import grants for external users from CSV file.
CSV format: DisplayName, SamAccountName, EmailAddress, SecurityGroups
Security groups are separated by ":"
"""
import csv
import io
from django.core.management.base import BaseCommand
from django.db import transaction
from access.models import AccessGrant, AccessGroup, ExternalUser


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


def extract_first_3_words(name):
    """Extract first 3 words from name."""
    if not name:
        return ''
    words = name.split()
    return ' '.join(words[:3])


def find_external_user_by_name(display_name):
    """
    Try to find external user by name with fuzzy matching.
    1. Exact match (first 3 words)
    2. By last name (surname)
    """
    # Step 1: Exact match with first 3 words
    short_name = extract_first_3_words(display_name)
    if short_name:
        try:
            return ExternalUser.objects.get(full_name=short_name)
        except ExternalUser.DoesNotExist:
            pass
    
    # Step 2: Try to match by last name (first word)
    words = display_name.split()
    if words:
        surname = words[0].strip()
        matches = list(ExternalUser.objects.filter(full_name__icontains=surname))
        
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Multiple matches - try to find best match by checking first name
            if len(words) >= 2:
                firstname = words[1].strip()
                for m in matches:
                    if firstname.lower() in m.full_name.lower():
                        return m
    
    return None


class Command(BaseCommand):
    help = 'Import grants for external users from CSV file'

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

            # Extract first 3 words
            full_name = extract_first_3_words(display_name)
            groups = parse_csv_groups(security_groups_str)

            if not groups:
                skipped_rows += 1
                continue

            user_groups.append({
                'display_name': display_name,
                'full_name': full_name,
                'groups': groups,
            })

        self.stdout.write(f'Parsed {len(user_groups)} users with groups ({skipped_rows} rows skipped)')

        # Find all access groups
        all_groups = dict(AccessGroup.objects.values_list('name', 'pk'))
        self.stdout.write(f'Found {len(all_groups)} access groups in database')

        # Process grants
        created = 0
        updated = 0
        not_found = 0
        group_not_found = 0
        errors = []
        matched_fuzzy = 0

        for user_data in user_groups:
            display_name = user_data['display_name']
            full_name = user_data['full_name']
            groups = user_data['groups']

            # Find external user by name (with fuzzy matching)
            external_user = find_external_user_by_name(display_name)
            
            if not external_user:
                not_found += 1
                continue

            # If we got here by fuzzy match (not exact), count it
            if external_user.full_name != full_name:
                matched_fuzzy += 1

            # Create grants for each group
            for group_name in groups:
                if group_name not in all_groups:
                    group_not_found += 1
                    continue

                group_id = all_groups[group_name]

                try:
                    # Check if grant already exists
                    existing = AccessGrant.objects.filter(
                        external_user=external_user,
                        group_id=group_id,
                        grant_type='external',
                        is_active=True,
                    ).first()

                    if existing:
                        # Update existing grant
                        existing.justification = f'Импортировано из {csv_file}'
                        existing.save()
                        updated += 1
                    else:
                        # Create new grant
                        AccessGrant.objects.create(
                            external_user=external_user,
                            group_id=group_id,
                            grant_type='external',
                            justification=f'Импортировано из {csv_file}',
                            is_active=True,
                        )
                        created += 1
                except Exception as e:
                    errors.append(f'Error creating grant for {full_name} -> {group_name}: {e}')

        # Print summary
        self.stdout.write(self.style.SUCCESS(f'\nImport completed!'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created}'))
        self.stdout.write(self.style.SUCCESS(f'  Updated: {updated}'))
        self.stdout.write(f'  Matched (fuzzy): {matched_fuzzy}')
        self.stdout.write(f'  Not found (external users): {not_found}')
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
