# Generated migration for TrainingCategory

from django.db import migrations, models


def create_default_category(apps, schema_editor):
    """Create default category and assign all existing training types to it."""
    TrainingCategory = apps.get_model('training', 'TrainingCategory')
    TrainingType = apps.get_model('training', 'TrainingType')
    
    # Create default category
    default_category, created = TrainingCategory.objects.get_or_create(
        name='Информационная безопасность',
        defaults={
            'description': 'Категория по умолчанию для всех типов обучения',
            'is_active': True,
        }
    )
    
    # Assign all existing training types to this category
    TrainingType.objects.filter(category__isnull=True).update(category=default_category)


class Migration(migrations.Migration):

    dependencies = [
        ('training', '0004_alter_training_skillspace_group_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrainingCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=255, verbose_name='Название')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлён')),
            ],
            options={
                'verbose_name': 'Категория обучения',
                'verbose_name_plural': 'Категории обучения',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='trainingtype',
            name='category',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='training_types',
                to='training.trainingcategory',
                verbose_name='Категория',
            ),
        ),
        migrations.RunPython(create_default_category, migrations.RunPython.noop),
    ]
