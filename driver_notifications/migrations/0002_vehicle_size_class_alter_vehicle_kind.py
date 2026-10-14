from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('driver_notifications', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehicle',
            name='size_class',
            field=models.CharField(blank=True, choices=[('S', 'S'), ('M', 'M'), ('L', 'L'), ('XL', 'XL'), ('XXL', 'XXL'), ('3XL', '3XL'), ('FURA', 'FURA'), ('CUSTOM', 'CUSTOM')], default='', max_length=10),
        ),
        migrations.AlterField(
            model_name='vehicle',
            name='kind',
            field=models.CharField(choices=[('tent', 'Tent'), ('van', 'Furgon'), ('refrigerator', 'Refrijerator'), ('isothermal', 'Izotermik'), ('flatbed', 'Bort / platforma'), ('tanker', 'Sisterna'), ('dump', 'Samosval'), ('lowbed', 'Tral'), ('container', 'Konteyner'), ('other', 'Boshqa')], max_length=30),
        ),
    ]
