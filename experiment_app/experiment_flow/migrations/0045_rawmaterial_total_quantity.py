from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0044_rawmaterialtype'),
    ]

    operations = [
        migrations.AddField(
            model_name='rawmaterial',
            name='total_quantity',
            field=models.DecimalField(blank=True, decimal_places=4, help_text='Total quantity received', max_digits=14, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0'))]),
        ),
        migrations.AddField(
            model_name='rawmaterial',
            name='total_unit',
            field=models.CharField(blank=True, help_text='Unit for the total quantity', max_length=50, null=True),
        ),
    ]
