from django.db import migrations, models
import django.db.models.deletion


def migrate_parent_fields_to_links(apps, schema_editor):
    ExperimentStep = apps.get_model("experiment_flow", "ExperimentStep")
    ExperimentStepLink = apps.get_model("experiment_flow", "ExperimentStepLink")

    links = []
    for step in ExperimentStep.objects.exclude(parent_id__isnull=True).only("id", "parent_id"):
        links.append(
            ExperimentStepLink(
                parent_step_id=step.parent_id,
                child_step_id=step.id,
            )
        )

    if links:
        ExperimentStepLink.objects.bulk_create(links, ignore_conflicts=True)


def migrate_links_to_parent_fields(apps, schema_editor):
    ExperimentStep = apps.get_model("experiment_flow", "ExperimentStep")
    ExperimentStepLink = apps.get_model("experiment_flow", "ExperimentStepLink")

    for step in ExperimentStep.objects.all().only("id"):
        first_link = (
            ExperimentStepLink.objects
            .filter(child_step_id=step.id)
            .order_by("parent_step_id")
            .first()
        )
        ExperimentStep.objects.filter(id=step.id).update(
            parent_id=first_link.parent_step_id if first_link else None
        )


class Migration(migrations.Migration):

    dependencies = [
        ("experiment_flow", "0037_rename_legacy_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExperimentStepLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                (
                    "child_step",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_links",
                        to="experiment_flow.experimentstep",
                    ),
                ),
                (
                    "parent_step",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outgoing_links",
                        to="experiment_flow.experimentstep",
                    ),
                ),
            ],
            options={
                "verbose_name": "Experiment Step Link",
                "verbose_name_plural": "Experiment Step Links",
                "db_table": "experiment_flow_expsteplink",
            },
        ),
        migrations.AddField(
            model_name="experimentstep",
            name="parents",
            field=models.ManyToManyField(
                blank=True,
                related_name="children",
                through="experiment_flow.ExperimentStepLink",
                through_fields=("child_step", "parent_step"),
                to="experiment_flow.experimentstep",
            ),
        ),
        migrations.AddConstraint(
            model_name="experimentsteplink",
            constraint=models.UniqueConstraint(
                fields=("parent_step", "child_step"),
                name="unique_experiment_step_link",
            ),
        ),
        migrations.RunPython(migrate_parent_fields_to_links, migrate_links_to_parent_fields),
    ]
