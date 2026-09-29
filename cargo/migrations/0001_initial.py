import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('partners', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Load',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origin', models.CharField(max_length=150)),
                ('destination', models.CharField(max_length=150)),
                ('cargo_name', models.CharField(max_length=255)),
                ('vehicle_type', models.CharField(max_length=120)),
                ('weight_tons', models.DecimalField(decimal_places=2, max_digits=9, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('is_price_negotiable', models.BooleanField(default=True)),
                ('price_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('currency', models.CharField(choices=[('UZS', 'UZS'), ('USD', 'USD')], default='UZS', max_length=3)),
                ('contact_phone', models.CharField(max_length=16, validators=[django.core.validators.RegexValidator('^(?:\\+[1-9]\\d{7,14}|[1-9]\\d{8})$', 'Use a 9-digit local number or international format such as +998938086599.')])),
                ('alternate_phone', models.CharField(blank=True, max_length=16, validators=[django.core.validators.RegexValidator('^(?:\\+[1-9]\\d{7,14}|[1-9]\\d{8})$', 'Use a 9-digit local number or international format such as +998938086599.')])),
                ('pickup_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('open', 'Open'), ('closed', 'Closed')], default='open', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='loads', to='partners.company')),
                ('posted_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='posted_loads', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'constraints': [models.CheckConstraint(condition=models.Q(('is_price_negotiable', True), ('price_amount__isnull', False), _connector='OR'), name='load_price_or_negotiable')],
            },
        ),
    ]
