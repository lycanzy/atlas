from django.db import migrations, models


def backfill_received_date(apps, schema_editor):
    RawMaterial = apps.get_model('experiment_flow', 'RawMaterial')
    for material in RawMaterial.objects.filter(received_date__isnull=True):
        if material.created_on:
            material.received_date = material.created_on.date()
            if material.material_code:
                material.batch_number = f"{material.material_code.strip().upper()}-{material.received_date.strftime('%m%d%y')}"
            material.save(update_fields=['received_date', 'batch_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0034_rawmaterial_steprawmaterialusage_remove_components'),
    ]

    operations = [
        migrations.AddField(
            model_name='rawmaterial',
            name='received_date',
            field=models.DateField(blank=True, help_text='Date this raw material batch was received', null=True),
        ),
        migrations.AlterField(
            model_name='rawmaterial',
            name='batch_number',
            field=models.CharField(blank=True, help_text='Raw material batch number generated from material code and received date', max_length=80),
        ),
        migrations.AlterField(
            model_name='rawmaterial',
            name='material_name',
            field=models.CharField(blank=True, help_text='Raw material name', max_length=100, null=True),
        ),
        migrations.RunPython(backfill_received_date, migrations.RunPython.noop),
    ]
