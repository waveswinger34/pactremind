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
from utils import MESSAGES, network

import logging
log = logging.getLogger("Reminder")

from datetime import datetime

class PACT(object):
    def __init__(self):
        self.gateway = None
    
    def handle(self, message):
        sender = message.sender
        text = message.text
        
        IncomingMessage(received_at=message.received,
                        sender=sender,
                        text=text,
                        network=network(sender)).save()

        try:
            subject = Subject.objects.filter(phone_number=sender).get()
        except:
            subject = None
        
        if not subject:
            self.register(sender, message.received)
        elif subject.active and text.lower().startswith('stop'):
            self.deactivate(subject)
        else:
            self.send(sender, 
                      ('You are already registered. '
                       'To stop receiving messages, text STOP. Thanks.'))

    def register(self, phone_number, received_at=datetime.now()):
        subject = Subject(phone_number=phone_number,
                          received_at=received_at,
                          messages_left=6)
        if len(Subject.objects.all()) % 2 is 0:
            subject.message_id = random.randint(0, len(MESSAGES) - 1)
        else:
            subject.messages_left = 0
        subject.save()            
        
        self.send(phone_number, 'Thanks for registering.')
        
        today = datetime.today()
        cutoff = datetime(today.year, today.month, today.day, 15)
        if received_at < cutoff and subject.message_id:
            self.send_reminder(subject)

    def send_reminder(self, subject):
        if subject.messages_left >= 1:
            text = MESSAGES[subject.message_id]
            log.debug('>>> sending info: %s' % text)
            self.send(number=subject.phone_number, text=text)
            subject.messages_left -= 1
            subject.save()
            log.debug(">>  message sent: %s" % subject)
        else:
            log.debug('>> %s has no reminders left' % subject)

    def deacticate(self, subject, message=None):
        if not message:
            message = 'You will not receive any more messages from PACT'
        subject.active = False
        subject.save()
        self.send(subject.phone_number, message)
    
    def send_reminders(self):
        log.debug('Sending reminders ...')
        self.poll_gateway(False)
        subjects = Subject.objects.filter(active=True).\
                                   filter(messages_left__isnull=False).\
                                   filter(messages_left__gt=0)
        for subject in subjects:
            self.send_reminder(subject)
        self.poll_gateway()
        log.debug('Done sending reminders.')
            
    def send_final_messages(self):
        log.debug('Sending final mesasge ...')
        final_msg = 'Wohoo; that is your health tip ;)'
        subjects = Subject.objects.filter(active=True).\
                                   filter(messages_left=0)
        today = datetime.today()
        subjects = [x for x in subjects if (today - x.received_at).days == 5]
        self.poll_gateway(False)
        for subject in subjects:                           
            self.deactivate(subject=subject, message=final_msg)
        self.poll_gateway(True)
        log.debug('Done sending final message.')
    
    def send(self, number, text): 
        # TODO save outgoing message in db   
        self.gateway.send(number, text)
        
    def poll_gateway(self, status=True):
        self.gateway.poll = status

        
class Gateway(object):
    """The Gateway itself."""

    def __init__(self, modem, app, interval=2):
        self.modem = modem
        self.app = app
        app.gateway = self
        self.interval = interval
        self.poll = True
        self.running = True

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
                    log.debug('Checking for next message...')
                    message = self.modem.next_message()
                    if message is not None:
                        self.app.handle(message)
                except KeyboardInterrupt:
                    log.debug('Ctrl-c received! Sending kill signal ...')
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
    app = PACT()
    gateway = Gateway(modem, app)
    
    log.debug("Listener setup")

    scheduler = ThreadedScheduler()
    schedule = [(07, 12), (07, 15), (07, 20)]
    
    for t in schedule:
        scheduler.add_daytime_task(action=app.send_reminders, 
                               taskname="Send Reminder", 
                               weekdays=range(1,8),
                               monthdays=None, 
                               processmethod=method.threaded, 
                               timeonday=t,
                               args=[], kw=None)
    
    scheduler.add_daytime_task(action=app.send_final_messages, 
                           taskname="Send Final Message", 
                           weekdays=range(1,8),
                           monthdays=None, 
                           processmethod=method.threaded, 
                           timeonday=(11, 40),
                           args=[], kw=None)
    
    scheduler.start()
    gateway.start()
    
    
if __name__ == "__main__":
    main()
    sys.exit(0)