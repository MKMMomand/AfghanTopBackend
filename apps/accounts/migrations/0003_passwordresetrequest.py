from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_approval_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordResetRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("mobile_number", models.CharField(db_index=True, max_length=20)),
                ("reset_token", models.CharField(max_length=64, unique=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("completed", "Completed"), ("expired", "Expired")], default="pending", max_length=20)),
                ("expires_at", models.DateTimeField()),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="password_reset_requests", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
