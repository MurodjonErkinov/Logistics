
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cargo', '0002_load_destination_lat_load_destination_lon_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='load',
            name='price_basis',
            field=models.CharField(choices=[('trip', 'Per trip'), ('ton', 'Per ton')], default='trip', max_length=8),
        ),
    ]
