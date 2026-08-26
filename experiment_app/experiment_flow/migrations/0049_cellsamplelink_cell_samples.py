import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0048_alter_rawmaterial_batch_number'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CellSampleLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('cell', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sample_links', to='experiment_flow.cell')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_cell_sample_links', to=settings.AUTH_USER_MODEL)),
                ('sample', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cell_links', to='experiment_flow.sample')),
            ],
            options={'ordering': ['sample__sample_name', 'sample_id']},
        ),
        migrations.AddConstraint(
            model_name='cellsamplelink',
            constraint=models.UniqueConstraint(fields=('cell', 'sample'), name='unique_cell_sample_link'),
        ),
        migrations.AddField(
            model_name='cell',
            name='samples',
            field=models.ManyToManyField(blank=True, related_name='cells', through='experiment_flow.CellSampleLink', to='experiment_flow.sample'),
        ),
    ]
