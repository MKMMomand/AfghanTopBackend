from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_default_topup_service(apps, schema_editor):
    ShopkeeperProfile = apps.get_model("shopkeepers", "ShopkeeperProfile")
    ServiceAccess = apps.get_model("shopkeepers", "ServiceAccess")
    for profile in ShopkeeperProfile.objects.all():
        ServiceAccess.objects.get_or_create(
            profile=profile,
            service_code="topup",
            defaults={
                "is_enabled": profile.status == "active",
                "cash_enabled": profile.status == "active",
                "credit_enabled": False,
                "credit_locked": True,
                "lock_reason": "Enable credit after review and deposit.",
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("shopkeepers", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="shopkeeperprofile",
            name="internal_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="shopkeeperprofile",
            name="manual_hold",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="shopkeeperprofile",
            name="manual_hold_reason",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name="ServiceAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("service_code", models.CharField(choices=[("topup", "Top-up"), ("data_bundle", "Data Bundle"), ("bill_payment", "Bill Payment"), ("money_transfer", "Money Transfer"), ("sim_services", "SIM Services"), ("other", "Other")], default="topup", max_length=30)),
                ("is_enabled", models.BooleanField(default=False)),
                ("cash_enabled", models.BooleanField(default=False)),
                ("credit_enabled", models.BooleanField(default=False)),
                ("credit_locked", models.BooleanField(default=True)),
                ("lock_reason", models.CharField(blank=True, max_length=255)),
                ("admin_note", models.CharField(blank=True, max_length=255)),
                ("credit_limit", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("available_credit", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("used_credit", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("overdue_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("allow_credit_for_topup_only", models.BooleanField(default=True)),
                ("auto_lock_on_overdue", models.BooleanField(default=True)),
                ("due_days", models.PositiveIntegerField(default=7)),
                ("next_due_date", models.DateTimeField(blank=True, null=True)),
                ("last_payment_at", models.DateTimeField(blank=True, null=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_accesses", to="shopkeepers.shopkeeperprofile")),
            ],
            options={"ordering": ["service_code", "profile_id"]},
        ),
        migrations.CreateModel(
            name="AccountAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("service_code", models.CharField(blank=True, max_length=30)),
                ("action", models.CharField(choices=[("application_created", "Application Created"), ("application_approved", "Application Approved"), ("application_rejected", "Application Rejected"), ("profile_activated", "Profile Activated"), ("service_enabled", "Service Enabled"), ("service_disabled", "Service Disabled"), ("credit_enabled", "Credit Enabled"), ("credit_locked", "Credit Locked"), ("credit_unlocked", "Credit Unlocked"), ("limit_changed", "Limit Changed"), ("payment_recorded", "Payment Recorded"), ("overdue_marked", "Overdue Marked")], max_length=30)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_logs", to="shopkeepers.shopkeeperprofile")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="account_audit_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AlterUniqueTogether(name="serviceaccess", unique_together={("profile", "service_code")}),
        migrations.RunPython(create_default_topup_service, migrations.RunPython.noop),
    ]
