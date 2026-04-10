from django.core.management.base import BaseCommand
from apps.topup.services import process_due_scheduled_topups


class Command(BaseCommand):
    help = "Process due scheduled top-ups."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        processed = process_due_scheduled_topups(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Processed {processed} scheduled top-up(s)."))
