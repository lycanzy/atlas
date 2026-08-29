from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('experiment_flow', '0049_cellsamplelink_cell_samples'),
    ]

    operations = [
        migrations.RenameField(
            model_name='cell',
            old_name='package_number',
            new_name='test_order_number',
        ),
        migrations.AlterModelOptions(
            name='cell',
            options={'ordering': ['test_order_number', 'barcode', 'id']},
        ),
    ]
