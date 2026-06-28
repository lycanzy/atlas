from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('experiment_flow', '0033_researchgroup_team_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='RawMaterial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('material_code', models.CharField(help_text='Raw material code', max_length=50)),
                ('batch_number', models.CharField(help_text='Raw material batch number', max_length=50)),
                ('material_type', models.CharField(blank=True, help_text='Raw material type/category', max_length=100, null=True)),
                ('material_name', models.CharField(help_text='Raw material name', max_length=100)),
                ('description', models.TextField(blank=True, help_text='Detailed description of the raw material', null=True)),
                ('supplier', models.CharField(blank=True, help_text='Supplier/vendor', max_length=200, null=True)),
                ('location', models.CharField(blank=True, help_text='Storage location', max_length=200, null=True)),
                ('notes', models.TextField(blank=True, help_text='Additional notes', null=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True, help_text='Whether the raw material is currently active/available')),
                ('owner', models.ForeignKey(blank=True, help_text='Raw material owner/responsible person', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='raw_materials', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Raw Material',
                'verbose_name_plural': 'Raw Materials',
                'ordering': ['material_code', 'batch_number'],
            },
        ),
        migrations.CreateModel(
            name='StepRawMaterialUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ('unit', models.CharField(blank=True, max_length=50, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('raw_material', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='step_usages', to='experiment_flow.rawmaterial')),
                ('step', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='raw_material_usages', to='experiment_flow.expstep')),
            ],
            options={
                'verbose_name': 'Step Raw Material Usage',
                'verbose_name_plural': 'Step Raw Material Usages',
                'ordering': ['raw_material__material_code', 'raw_material__batch_number'],
            },
        ),
        migrations.RemoveField(
            model_name='expstep',
            name='components',
        ),
        migrations.AddConstraint(
            model_name='rawmaterial',
            constraint=models.UniqueConstraint(fields=('material_code', 'batch_number'), name='unique_raw_material_code_batch'),
        ),
        migrations.AddConstraint(
            model_name='steprawmaterialusage',
            constraint=models.UniqueConstraint(fields=('step', 'raw_material'), name='unique_step_raw_material_usage'),
        ),
    ]
