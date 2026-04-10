from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("topup", "0003_scheduledtopup"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduledtopup",
            name="failure_reason",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="scheduledtopup",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="scheduledtopup",
            name="last_run_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="scheduledtopup",
            name="next_run_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="scheduledtopup",
            name="repeat_type",
            field=models.CharField(choices=[("once", "Once"), ("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")], default="once", max_length=20),
        ),
        migrations.AlterModelOptions(
            name="scheduledtopup",
            options={"ordering": ["next_run_at", "schedule_for", "-created_at"]},
        ),
        migrations.CreateModel(
            name="BulkTopupBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.CharField(blank=True, max_length=120)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("completed", "Completed"), ("partial", "Partial"), ("failed", "Failed")], default="pending", max_length=20)),
                ("total_items", models.PositiveIntegerField(default=0)),
                ("success_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("total_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bulk_topup_batches", to="shopkeepers.shopkeeperprofile")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="CustomerReminder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("mobile_number", models.CharField(max_length=20)),
                ("label", models.CharField(blank=True, max_length=120)),
                ("network", models.CharField(blank=True, max_length=50)),
                ("preferred_amount", models.DecimalField(decimal_places=2, default=25, max_digits=12)),
                ("reminder_at", models.DateTimeField()),
                ("reminder_type", models.CharField(choices=[("manual", "Manual"), ("weekly", "Weekly"), ("monthly", "Monthly"), ("smart", "Smart")], default="manual", max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("done", "Done"), ("missed", "Missed"), ("cancelled", "Cancelled")], default="pending", max_length=20)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("favorite", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reminders", to="topup.favoritenumber")),
                ("last_topup", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reminder_entries", to="topup.topuptransaction")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="customer_reminders", to="shopkeepers.shopkeeperprofile")),
            ],
            options={"ordering": ["reminder_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="BulkTopupItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("mobile_number", models.CharField(max_length=20)),
                ("network", models.CharField(blank=True, max_length=50)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("label", models.CharField(blank=True, max_length=120)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")], default="pending", max_length=20)),
                ("message", models.CharField(blank=True, max_length=255)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="topup.bulktopupbatch")),
                ("transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bulk_items", to="topup.topuptransaction")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model("topup", "ScheduledTopup").objects.filter(next_run_at__isnull=True).update(next_run_at=models.F("schedule_for")),
            reverse_code=migrations.RunPython.noop,
        ),
    ]
