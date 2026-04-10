from django.core.management.base import BaseCommand
from decouple import config as env

from apps.providers.models import TopUpProvider


class Command(BaseCommand):
    help = "Create or update the Send.af provider configuration from environment variables."

    def handle(self, *args, **options):
        token = env("SEND_AF_TOKEN", default="").strip()
        if not token:
            self.stderr.write(self.style.ERROR("SEND_AF_TOKEN is not set."))
            return

        provider, created = TopUpProvider.objects.update_or_create(
            code="sendaf",
            defaults={
                "name": env("SEND_AF_NAME", default="Send.af"),
                "base_url": env("SEND_AF_BASE_URL", default="https://www.send.af/api"),
                "auth_token": token,
                "priority": env("SEND_AF_PRIORITY", default=1, cast=int),
                "status": env("SEND_AF_STATUS", default="active"),
                "supports_auto_network_detection": True,
                "supported_networks": env("SEND_AF_SUPPORTED_NETWORKS", default="AWCC,Roshan,Etisalat,MTN,Salaam"),
                "extra_config": {
                    "timeout_seconds": env("SEND_AF_TIMEOUT_SECONDS", default=20, cast=int),
                    "min_amount": env("SEND_AF_MIN_AMOUNT", default=50, cast=int),
                    "max_amount": env("SEND_AF_MAX_AMOUNT", default=4000, cast=int),
                    "topup_path": "topup",
                    "wallet_path": "wallet",
                    "orderStatus_path": "orderStatus",
                },
            },
        )
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} provider {provider.name} ({provider.code})."))
