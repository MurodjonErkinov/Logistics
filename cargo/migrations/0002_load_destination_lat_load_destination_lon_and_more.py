
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cargo', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='load',
            name='destination_lat',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)]),
        ),
        migrations.AddField(
            model_name='load',
            name='destination_lon',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)]),
        ),
        migrations.AddField(
            model_name='load',
            name='origin_lat',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)]),
        ),
        migrations.AddField(
            model_name='load',
            name='origin_lon',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)]),
        ),
    ]
