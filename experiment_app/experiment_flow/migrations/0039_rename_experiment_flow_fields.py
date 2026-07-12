from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("experiment_flow", "0038_experimentsteplink"),
    ]

    operations = [
        migrations.RenameField(
            model_name="experiment",
            old_name="flow_name",
            new_name="experiment_code",
        ),
        migrations.RenameField(
            model_name="experiment",
            old_name="flow_description",
            new_name="experiment_description",
        ),
        migrations.RenameField(
            model_name="experiment",
            old_name="full_flow",
            new_name="full_experiment_code",
        ),
        migrations.RenameField(
            model_name="experiment",
            old_name="exp",
            new_name="project",
        ),
        migrations.AlterField(
            model_name="experiment",
            name="project",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="experiments",
                to="experiment_flow.project",
            ),
        ),
        migrations.RenameField(
            model_name="experimentstep",
            old_name="flow",
            new_name="experiment",
        ),
        migrations.AlterField(
            model_name="experimentstep",
            name="experiment",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="steps",
                to="experiment_flow.experiment",
            ),
        ),
        migrations.RenameField(
            model_name="sample",
            old_name="flow",
            new_name="step",
        ),
        migrations.AlterField(
            model_name="sample",
            name="step",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="samples",
                to="experiment_flow.experimentstep",
            ),
        ),
    ]
