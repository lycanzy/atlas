import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0045_rawmaterial_total_quantity'),
    ]

    operations = [
        migrations.CreateModel(
            name='CellTestItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name', 'id'],
            },
        ),
        migrations.AddField(
            model_name='cell',
            name='test_item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='cells', to='experiment_flow.celltestitem'),
        ),
    ]
