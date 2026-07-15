import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0040_add_sample_numbering'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('create', '新增'), ('update', '修改'), ('delete', '删除')], max_length=10)),
                ('entity_type', models.CharField(max_length=50)),
                ('object_id', models.CharField(blank=True, max_length=64)),
                ('object_repr', models.CharField(max_length=200)),
                ('summary', models.CharField(max_length=500)),
                ('changes', models.JSONField(blank=True, default=dict)),
                ('created_on', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Audit Log',
                'verbose_name_plural': 'Audit Logs',
                'ordering': ['-created_on', '-id'],
            },
        ),
    ]
