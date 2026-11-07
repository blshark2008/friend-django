from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('equipment', '0012_add_filter_keyword'),
    ]

    operations = [
        migrations.RunSQL(
            [
                # 1. Убираем NOT NULL constraint
                "ALTER TABLE equipment_equipment ALTER COLUMN serial_number DROP NOT NULL",
                # 2. Конвертируем пустые строки в NULL
                "UPDATE equipment_equipment SET serial_number = NULL WHERE serial_number = ''",
                # 3. Убираем дубликаты: для каждого дубликата оставляем первый, остальные NULL
                """
                WITH duplicates AS (
                    SELECT id,
                           ROW_NUMBER() OVER (PARTITION BY serial_number ORDER BY id) as rn
                    FROM equipment_equipment
                    WHERE serial_number IS NOT NULL
                )
                UPDATE equipment_equipment
                SET serial_number = NULL
                FROM duplicates
                WHERE equipment_equipment.id = duplicates.id AND duplicates.rn > 1
                """,
                # 4. Добавляем unique constraint
                "ALTER TABLE equipment_equipment ADD CONSTRAINT equipment_equipment_serial_number_unique UNIQUE (serial_number)",
            ],
            # Обратные операции (для отката)
            [
                "ALTER TABLE equipment_equipment DROP CONSTRAINT equipment_equipment_serial_number_unique",
                "ALTER TABLE equipment_equipment ALTER COLUMN serial_number SET NOT NULL",
            ],
        ),
    ]
