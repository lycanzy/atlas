from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0051_project_authorized_users_userprofile_is_team_owner'),
    ]

    operations = [
        migrations.AlterField(
            model_name='experimentstep',
            name='status',
            field=models.CharField(
                choices=[
                    ('Planned', 'Planned'),
                    ('InProgress', 'In Progress'),
                    ('Canceled', 'Canceled'),
                    ('Completed', 'Completed'),
                ],
                default='Planned',
                max_length=10,
            ),
        ),
    ]
