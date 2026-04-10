import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("providers", "0003_topupprovider_daily_cap_and_more"),
        ("shopkeepers", "0003_shop_profile_designer_fields"),
        ("topup", "0002_favorite_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledTopup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("mobile_number", models.CharField(max_length=20)),
                ("network", models.CharField(blank=True, max_length=50)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("schedule_for", models.DateTimeField()),
                ("status", models.CharField(choices=[("scheduled", "Scheduled"), ("sent", "Sent"), ("cancelled", "Cancelled"), ("failed", "Failed")], default="scheduled", max_length=20)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("last_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scheduled_entries", to="topup.topuptransaction")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scheduled_topups", to="shopkeepers.shopkeeperprofile")),
            ],
            options={"ordering": ["schedule_for", "-created_at"]},
        ),
    ]
