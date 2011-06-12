#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import logging
import traceback
import random
import time
from kronos import method, ThreadedScheduler

import settings
from django.core.management import setup_environ
setup_environ(settings)

from reminder.models import *

from pygsm import GsmModem
from utils import *

log = logging.getLogger("Reminder")


class Gateway:
    """The Gateway itself."""

    def __init__(self, modem, interval=2):
        self.running = True
        self.poll = True
        self.modem = modem
        self.interval = interval

    def handle(self, msg):
        sms = IncomingMessage(received_at=msg.received,
                              sender=msg.sender,
                              text=msg.text,
                              network=network(msg.sender))
        sms.save()

        subject = Subject.objects.filter(phone_number=msg.sender)
        
        if not subject:
            subject = Subject(phone_number=msg.sender,
                              received_at=msg.received,
                              messages_left=6)
            if len(Subject.objects.all()) % 2 is 0:
                subject.message_id = random.randint(0, 2)
            subject.save()            
            self.respond(msg, "Thanks for registering.")
        elif msg.text.lower() is 'stop' and subject.active:
            subject.active = False
            subject.save()
            self.respond(msg, 
                         'You will not receive any more messages from PACT')
        else:
            self.respond(msg, 
                         ("You are already registered. "
                          "To stop receiving messages, text STOP. Thanks."))

    def respond(self, msg, text):
        self.send(msg.sender, text)
        
    def send(self, number, text):
        log.debug('Sending: %s' % text)
        self.modem.send_sms(number, text)
        return self.modem.wait_for_network()
        
    def start(self):
        """Start the gateway."""
        self._run()

    def stop(self):
        """Remove all pending tasks and stop the Gateway."""
        self.running = False

    def _run(self):
        # Low-level run method to do the actual listening loop.
        while self.running:
            if self.poll:
                try:
                    print "Checking for message..."
                    msg = self.modem.next_message()
                    if msg is not None:
                        self.handle(msg)
                except KeyboardInterrupt:
                    print "Ctrl-c received! Sending kill to threads..."
                    self.stop()
                except Exception, x:
                    print >>sys.stderr, "ERROR DURING GATEWAY EXECUTION", x
                    print >>sys.stderr, "".join(
                        traceback.format_exception(*sys.exc_info()))
                    print >>sys.stderr, "-" * 20
            if self.running:
                time.sleep(self.interval)


def main():
    #TODO: parse port from script arg
    port = '/dev/tty.HUAWEIMobile-Modem'
    logger = GsmModem.debug_logger
    modem = GsmModem(port=port, logger=logger).boot()
    
    log.debug("Waiting for network...")
    tmp = modem.wait_for_network()
    
    gateway = Gateway(modem)
    
    log.debug("Listener setup")

    scheduler = ThreadedScheduler()

    def send_reminder(gateway):
        print 'Sending reminders ...'
        gateway.poll = False
        subjects = Subject.objects.filter(active=True).\
                                   filter(messages_left__isnull=False).\
                                   filter(messages_left__gt=0)
                                           
        for subject in subjects:
            text = MESSAGES[subject.message_id]
            print '>>> sending info: %s' % text
            gateway.send(number=subject.phone_number, text=text)
            subject.messages_left -= 1
            subject.save()
            print ">>  message sent: %s" % subject
        print 'Done sending reminders.'
        gateway.poll = True
            
    schedule = [(07, 12), (07, 15), (07, 20)]
    
    for t in schedule:
        scheduler.add_daytime_task(action=send_reminder, 
                               taskname="Send Reminder", 
                               weekdays=range(1,8),
                               monthdays=None, 
                               processmethod=method.threaded, 
                               timeonday=t,
                               args=[gateway], kw=None)
    scheduler.start()
    gateway.start()
    
    
if __name__ == "__main__":
    import sys
    main()
    sys.exit(0)
    






