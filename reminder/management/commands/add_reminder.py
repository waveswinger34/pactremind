from django.core.management.base import BaseCommand, CommandError
from rapidsms.contrib.scheduler.models import EventSchedule

class Command(BaseCommand):
    args = '<min min ...>'
    help = 'Adds schedule based on minutes for testing reminder'

    def handle(self, *args, **options):
        try:
            xs = set([int(x) for x in list(args)])
            task = EventSchedule(callback='reminder.tasks.broadcast',
                                 minutes=xs)
            task.save()
        except:
            raise CommandError
        
        self.stdout.write('Task <%s> added.' % (task.pk))
