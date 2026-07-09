from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Driver",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("phone", models.CharField(max_length=24)),
                ("license_number", models.CharField(max_length=64, unique=True)),
                ("home_base", models.CharField(max_length=120)),
                ("status", models.CharField(choices=[("available", "Available"), ("assigned", "Assigned"), ("on_trip", "On trip"), ("off_duty", "Off duty"), ("suspended", "Suspended")], default="available", max_length=24)),
                ("rating", models.DecimalField(decimal_places=2, default=4.5, max_digits=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Vehicle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("registration_number", models.CharField(max_length=24, unique=True)),
                ("make", models.CharField(max_length=80)),
                ("model", models.CharField(max_length=80)),
                ("category", models.CharField(default="Sedan", max_length=40)),
                ("current_city", models.CharField(max_length=120)),
                ("status", models.CharField(choices=[("idle", "Idle"), ("en_route_pickup", "En route to pickup"), ("active_trip", "Active trip"), ("maintenance", "Maintenance"), ("offline", "Offline")], default="idle", max_length=24)),
                ("permit_expires_on", models.DateField()),
                ("insurance_expires_on", models.DateField()),
                ("pollution_expires_on", models.DateField()),
                ("fitness_expires_on", models.DateField()),
                ("odometer_km", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_driver", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vehicles", to="fleet.driver")),
            ],
        ),
        migrations.CreateModel(
            name="Trip",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_name", models.CharField(max_length=120)),
                ("pickup_city", models.CharField(max_length=120)),
                ("drop_city", models.CharField(max_length=120)),
                ("pickup_at", models.DateTimeField()),
                ("estimated_drop_at", models.DateTimeField()),
                ("status", models.CharField(choices=[("requested", "Requested"), ("assigned", "Assigned"), ("en_route_pickup", "En route to pickup"), ("active", "Active"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="requested", max_length=24)),
                ("ota_source", models.CharField(blank=True, max_length=80)),
                ("fare_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("driver", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="trips", to="fleet.driver")),
                ("vehicle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="trips", to="fleet.vehicle")),
            ],
            options={"ordering": ["pickup_at"]},
        ),
    ]

