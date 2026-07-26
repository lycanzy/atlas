from django.db import migrations, models


def seed_existing_material_types(apps, schema_editor):
    RawMaterial = apps.get_model('experiment_flow', 'RawMaterial')
    RawMaterialType = apps.get_model('experiment_flow', 'RawMaterialType')
    existing_names = (
        RawMaterial.objects.exclude(material_type__isnull=True)
        .exclude(material_type='')
        .values_list('material_type', flat=True)
        .distinct()
    )
    RawMaterialType.objects.bulk_create(
        [RawMaterialType(name=name.strip()) for name in existing_names if name.strip()],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0043_cell'),
    ]

    operations = [
        migrations.CreateModel(
            name='RawMaterialType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Raw Material Type',
                'verbose_name_plural': 'Raw Material Types',
                'ordering': ['name'],
            },
        ),
        migrations.RunPython(seed_existing_material_types, migrations.RunPython.noop),
    ]
