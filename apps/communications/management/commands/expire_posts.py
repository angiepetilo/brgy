from django.core.management.base import BaseCommand
from apps.communications.services import expire_posts_service


class Command(BaseCommand):
    help = "Idempotent daily command to mark posts past valid_until as expired."

    def handle(self, *args, **options):
        count = expire_posts_service()
        self.stdout.write(self.style.SUCCESS(f"Successfully marked {count} expired post(s)."))
