"""
Management command to import employees from CSV file into ExternalUser model.
CSV format: ФИО, Должность, Email, Телефон
Lines like "Администрация,,," are department headers.
Position format: "Department-Position"
Only first 3 words of ФИО are used.
"""
import csv
import io
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from access.models import Organization, Contract, ExternalUser


def parse_csv(filepath):
    """Parse CSV file and return list of employee dicts with department tracking."""
    employees = []
    current_department = ""

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Use csv reader to handle quoted fields with newlines
    reader = csv.reader(io.StringIO(content))
    header = next(reader)  # skip header

    for row in reader:
        # Pad row to 4 columns if needed
        while len(row) < 4:
            row.append('')

        fio_raw = row[0].strip()
        position_raw = row[1].strip()
        email_raw = row[2].strip()
        phone_raw = row[3].strip()

        # Skip empty rows
        if not fio_raw:
            continue

        # Check if this is a department header (only first column has content, rest empty)
        # Department names don't look like full names (no patronymic typically, but let's check)
        # A department line has empty position, email, phone
        if not position_raw and not email_raw and not phone_raw:
            # Could be a department header or a person with no position
            # Department names are typically short (1-3 words, no patronymic pattern)
            # But "Администрация" is clearly a department
            # Heuristic: if the row has only 1 meaningful column and it's short-ish, it's a department
            # Also, if we see lines like "Женская консультация №1 (пр.Кузнецкстроевский, 34)" it's clearly a dept
            current_department = fio_raw
            continue

        # This is an employee row
        # Extract only first 3 words from ФИО
        fio_words = fio_raw.split()
        if len(fio_words) >= 3:
            full_name = ' '.join(fio_words[:3])
        else:
            full_name = fio_raw

        # Clean up position - remove leading "-," or similar
        if position_raw == '-' or position_raw == ',-':
            position_raw = ''

        # Build department-based position
        if current_department and position_raw:
            final_position = f"{current_department}-{position_raw}"
        elif position_raw:
            final_position = position_raw
        else:
            final_position = ""

        # Clean email - take first email if multiple
        email = ''
        if email_raw:
            emails = [e.strip() for e in email_raw.split('\n') if '@' in e]
            if emails:
                email = emails[0]

        # Clean phone
        phone = phone_raw.strip() if phone_raw else ''

        employees.append({
            'full_name': full_name,
            'department': current_department,
            'position': final_position,
            'email': email,
            'phone': phone,
        })

    return employees


def clean_phone(phone):
    """Clean phone number to keep only digits and basic formatting."""
    if not phone:
        return ''
    # Keep digits, parentheses, dashes, spaces
    cleaned = ''
    for ch in phone:
        if ch.isdigit() or ch in '()- ':
            cleaned += ch
    return cleaned.strip()


class Command(BaseCommand):
    help = 'Import employees from CSV into ExternalUser'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')

    def handle(self, *args, **options):
        csv_file = options['csv_file']

        # Find organization by INN
        inn = '4208001748'
        try:
            org = Organization.objects.get(inn=inn)
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Organization with INN {inn} not found!'))
            return

        self.stdout.write(f'Found organization: {org.name} (INN: {org.inn})')

        # Find the most recent active contract for this organization
        contracts = Contract.objects.filter(
            organization=org,
        ).order_by('-date_to')

        active_contract = None
        for c in contracts:
            if c.status == Contract.Status.ACTIVE:
                active_contract = c
                break

        if not active_contract:
            # Try any contract that's not closed/terminated
            for c in contracts:
                if c.status not in [Contract.Status.CLOSED, Contract.Status.TERMINATED]:
                    active_contract = c
                    break

        if not active_contract:
            self.stdout.write(self.style.ERROR(f'No suitable contract found for organization {org.name}!'))
            self.stdout.write('Available contracts:')
            for c in contracts:
                self.stdout.write(f'  - {c.number} от {c.date_from.strftime("%d.%m.%Y")} (status: {c.status})')
            return

        self.stdout.write(f'Using contract: {active_contract.number} от {active_contract.date_from.strftime("%d.%m.%Y")}')

        # Parse CSV
        self.stdout.write(f'Parsing CSV file: {csv_file}')
        employees = parse_csv(csv_file)
        self.stdout.write(f'Parsed {len(employees)} employees')

        # Import employees
        created = 0
        updated = 0
        skipped_empty = 0
        errors = []

        with transaction.atomic():
            for emp in employees:
                # Skip if no position and no department
                if not emp['position'] and not emp['department']:
                    skipped_empty += 1
                    continue

                try:
                    obj, is_new = ExternalUser.objects.update_or_create(
                        contract=active_contract,
                        full_name=emp['full_name'],
                        defaults={
                            'user_type': ExternalUser.UserType.CONTRACTOR_EMPLOYEE,
                            'department': emp['department'],
                            'position': emp['position'],
                            'id_doc_no': '',
                            'is_active': True,
                        }
                    )
                    if is_new:
                        created += 1
                    else:
                        updated += 1
                except Exception as e:
                    errors.append(f'Error processing {emp["full_name"]}: {e}')

        self.stdout.write(self.style.SUCCESS(f'\nImport completed!'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created}'))
        self.stdout.write(f'  Updated: {updated}')
        self.stdout.write(f'  Skipped (empty): {skipped_empty}')
        if errors:
            self.stdout.write(self.style.ERROR(f'  Errors: {len(errors)}'))
            for err in errors[:10]:
                self.stdout.write(f'    - {err}')
