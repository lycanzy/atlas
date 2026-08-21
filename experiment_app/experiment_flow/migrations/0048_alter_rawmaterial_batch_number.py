from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0047_experimentstep_owner'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rawmaterial',
            name='batch_number',
            field=models.CharField(help_text='Raw material batch number', max_length=80),
        ),
    ]
