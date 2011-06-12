from django.core.management.base import NoArgsCommand
from rapidsms.contrib.scheduler.models import EventSchedule

class Command(NoArgsCommand):
    help = 'Removes current reminder schedule'

    def handle_noargs(self, *args, **options):
        schedules = EventSchedule.objects.all()
        schedules.delete()
        self.stdout.write('Clean as a whistle ;)\n')
