from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0050_rename_cell_package_number'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='authorized_users',
            field=models.ManyToManyField(
                blank=True,
                help_text='Additional users explicitly granted access to this project.',
                related_name='authorized_projects',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='is_team_owner',
            field=models.BooleanField(
                default=False,
                help_text="May manage project-level access for projects in this user's Team.",
            ),
        ),
    ]
