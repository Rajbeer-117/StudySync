"""Send reminders for confirmed sessions starting soon. Run hourly from cron / a scheduler."""
from django.core.management.base import BaseCommand

from core import services


class Command(BaseCommand):
    help = 'Notify students and tutors about confirmed sessions starting within --hours (default 24).'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24)

    def handle(self, *args, **options):
        sent = services.send_due_reminders(hours=options['hours'])
        self.stdout.write(self.style.SUCCESS(f'{sent} reminder(s) sent.'))
