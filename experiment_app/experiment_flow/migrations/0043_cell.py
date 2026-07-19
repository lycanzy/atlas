from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0042_expand_auditlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cell',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('package_number', models.CharField(db_index=True, max_length=100)),
                ('barcode', models.CharField(max_length=100, unique=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('step', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cells', to='experiment_flow.experimentstep')),
            ],
            options={
                'ordering': ['package_number', 'barcode', 'id'],
            },
        ),
    ]
