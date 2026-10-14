from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cargo', '0003_load_price_basis'),
    ]

    operations = [
        migrations.AddField(
            model_name='load',
            name='vehicle_kind',
            field=models.CharField(blank=True, choices=[('tent', 'Tent'), ('van', 'Furgon'), ('refrigerator', 'Refrijerator'), ('isothermal', 'Izotermik'), ('flatbed', 'Bort / platforma'), ('tanker', 'Sisterna'), ('dump', 'Samosval'), ('lowbed', 'Tral'), ('container', 'Konteyner'), ('other', 'Boshqa')], default='', max_length=30),
        ),
        migrations.AddField(
            model_name='load',
            name='vehicle_size',
            field=models.CharField(blank=True, choices=[('S', 'S'), ('M', 'M'), ('L', 'L'), ('XL', 'XL'), ('XXL', 'XXL'), ('3XL', '3XL'), ('FURA', 'FURA'), ('CUSTOM', 'CUSTOM')], default='', max_length=10),
        ),
    ]
