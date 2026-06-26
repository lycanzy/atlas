from django.db import migrations


DEFAULT_TEAMS = [
    "Physical Characterization",
    "Anode-free Engineering",
    "Cathode Engineering",
]


def seed_default_teams(apps, schema_editor):
    ResearchGroup = apps.get_model("experiment_flow", "ResearchGroup")
    for group_name in DEFAULT_TEAMS:
        ResearchGroup.objects.get_or_create(group_name=group_name)


class Migration(migrations.Migration):

    dependencies = [
        ("experiment_flow", "0031_alter_exp_options_alter_expflow_options_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_default_teams, migrations.RunPython.noop),
    ]
