#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import time
import sys
import traceback
import random

from kronos import method, ThreadedScheduler
from pygsm import GsmModem

import settings
from django.core.management import setup_environ
setup_environ(settings)

from reminder.models import *
from utils import *

import logging
log = logging.getLogger("Reminder")

from datetime import datetime


class Gateway:
    """The Gateway itself."""

    def __init__(self, modem, interval=2):
        self.modem = modem
        self.interval = interval
        self.poll = True
        self.running = True

    def handle(self, msg):
        sms = IncomingMessage(received_at=msg.received,
                              sender=msg.sender,
                              text=msg.text,
                              network=network(msg.sender))
        sms.save()

        subject = None
        try:
            subject = Subject.objects.filter(phone_number=msg.sender).get()
        except: pass
        
        if not subject:
            subject = Subject(phone_number=msg.sender,
                              received_at=msg.received,
                              messages_left=6)
            if len(Subject.objects.all()) % 2 is 0:
                subject.message_id = random.randint(0, 2)
            subject.save()            
            self.respond(msg, "Thanks for registering.")
        elif msg.text.lower().strip() == 'stop' and subject.active:
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
        s = self.modem.wait_for_network()
        return s
        
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
                    log.debug("Ctrl-c received! Sending kill to threads...")
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
        log.debug('Sending reminders ...')
        
        # stop polling on the gateway for new messages
        gateway.poll = False
        
        subjects = Subject.objects.filter(active=True).\
                                   filter(messages_left__isnull=False).\
                                   filter(messages_left__gt=0)
        for subject in subjects:
            text = MESSAGES[subject.message_id]
            log.debug('>>> sending info: %s' % text)
            gateway.send(number=subject.phone_number, text=text)
            subject.messages_left -= 1
            subject.save()
            log.debug(">>  message sent: %s" % subject)
        log.debug('Done sending reminders.')
        # restart polling for new messages
        gateway.poll = True
            
    def send_final_message(gateway):
        print('This is a print statement in the final message')
        log.debug('Sending final mesasge ...')
        final_msg = 'Wohoo; that is your health tip ;)'
        subjects = Subject.objects.filter(active=True).\
                                   filter(messages_left=0)
        today = datetime.today()
        xs = [(x, (today - x.received_at).days) for x in subjects]
        
        print '>>>> subject-days: %s' % xs
        
        subjects = [x for x in subjects if (today - x.received_at).days == 5]
        gateway.poll = False
        for subject in subjects:                           
            gateway.send(number=subject.phone_number, text=final_msg)
            subject.active = False
            subject.save()
        gateway.poll = True
        log.debug('Done sending final message.')
    
    schedule = [(07, 12), (07, 15), (07, 20)]
    
    for t in schedule:
        scheduler.add_daytime_task(action=send_reminder, 
                               taskname="Send Reminder", 
                               weekdays=range(1,8),
                               monthdays=None, 
                               processmethod=method.threaded, 
                               timeonday=t,
                               args=[gateway], kw=None)
    
    scheduler.add_daytime_task(action=send_final_message, 
                           taskname="Send Final Message", 
                           weekdays=range(1,8),
                           monthdays=None, 
                           processmethod=method.threaded, 
                           timeonday=(11, 40),
                           args=[gateway], kw=None)
    
    scheduler.start()
    gateway.start()
    
    
if __name__ == "__main__":
    main()
    sys.exit(0)