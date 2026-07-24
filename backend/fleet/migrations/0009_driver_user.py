from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("fleet", "0008_vehicle_baseline_mileage_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="driver",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="driver_profile",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
