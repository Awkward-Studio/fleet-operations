from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_odometer_confirmation(apps, schema_editor):
    TripChecklist = apps.get_model("fleet", "TripChecklist")
    now = timezone.now()
    TripChecklist.objects.update(
        start_driver_confirmed=True,
        start_confirmed_at=now,
        start_client_version="legacy-backfill",
    )
    TripChecklist.objects.filter(end_odometer_km__isnull=False).update(
        end_driver_confirmed=True,
        end_confirmed_at=now,
        end_client_version="legacy-backfill",
    )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("fleet", "0018_alter_contractrate_duty_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tripchecklist",
            name="start_reading_source",
            field=models.CharField(
                choices=[
                    ("MANUAL", "Manual"),
                    ("OCR_CONFIRMED", "OCR confirmed"),
                    ("OCR_CORRECTED", "OCR corrected"),
                ],
                default="MANUAL",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="start_driver_confirmed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="start_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="start_expected_reference_km",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="start_client_ocr_decision",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ACCEPTED", "Accepted"),
                    ("NEEDS_REVIEW", "Needs review"),
                    ("NO_READING", "No reading"),
                ],
                max_length=24,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="start_client_version",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="start_override_reason",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="start_overridden_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="overridden_trip_start_odometers",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="end_reading_source",
            field=models.CharField(
                choices=[
                    ("MANUAL", "Manual"),
                    ("OCR_CONFIRMED", "OCR confirmed"),
                    ("OCR_CORRECTED", "OCR corrected"),
                ],
                default="MANUAL",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="end_driver_confirmed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="end_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="end_expected_reference_km",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="end_client_ocr_decision",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ACCEPTED", "Accepted"),
                    ("NEEDS_REVIEW", "Needs review"),
                    ("NO_READING", "No reading"),
                ],
                max_length=24,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="end_client_version",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="end_override_reason",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="tripchecklist",
            name="end_overridden_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="overridden_trip_end_odometers",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_odometer_confirmation, migrations.RunPython.noop),
    ]
