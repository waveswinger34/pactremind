#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import sys
import random

from gsm import Modem
from gsm import Gateway
from datetime import datetime
from kronos import method, ThreadedScheduler

import settings
from django.core.management import setup_environ
setup_environ(settings)

from reminder.models import Subject, IncomingMessage
from utils import MESSAGES, network, _logger

log = _logger('Reminder App')


class PACT(object):
    def __init__(self, scheduler):
        self.gateway = None
        self.scheduler = scheduler
    
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
        if len(Subject.objects.all()) % 2 is 3: #new
            subject.message_id = random.randint(0, len(MESSAGES) - 1)
        subject.save()            
        self.send(phone_number, 
                  'Thanks for registering for Mobile Health Information.')
        today = datetime.today()
        cutoff = datetime(today.year, today.month, today.day, 15)
        if received_at < cutoff and subject.message_id: #new after and
            now  = datetime.now()
            def send_reminder_in_15():
                log.debug('Sending out task scheduled at: %s' % now)
                self.send_reminder(subject)
            self.scheduler.add_single_task(action=send_reminder_in_15,
                                           initialdelay=900, # 15 * 60 secs=900
                                           taskname='Send delayed first msg',
                                           processmethod=method.threaded,
                                           args=[], kw={})
            

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

    def deactivate(self, subject, message=None):
        if not message:
            message = ('You will not receive any more messages from '
                       'Mobile Health')
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
        final_msg = 'To prevent malaria, sleep under a mosquito net!'
        subjects = Subject.objects.filter(active=True).\
                                   filter(messages_left=0)
        today = datetime.today()
        subjects = [x for x in subjects if (today - x.received_at).days == 2]
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


def bootstrap(options):
    logger = Modem.debug_logger
    modem = Modem(port=options.port or settings.SMS_MODEM_PORT,
                     logger=logger).boot()
    
    log.debug("Waiting for network...")
    modem.wait_for_network()
    
    scheduler = ThreadedScheduler()
    app = PACT(scheduler)
    gateway = Gateway(modem, app)
    
    def add_task(taskname, action, timeonday):
        scheduler.add_daytime_task(action=action, 
                                   taskname=taskname, 
                                   weekdays=range(1,8),
                                   monthdays=None, 
                                   processmethod=method.threaded, 
                                   timeonday=timeonday,
                                   args=[], kw=None)
    
    for t in settings.SEND_REMINDERS_SCHEDULE:
        add_task('Send Reminders', app.send_reminders, t)
    if settings.SEND_FINAL_MESSAGES_TIME:
        add_task('Send Final Messages', app.send_final_messages,
                 settings.SEND_FINAL_MESSAGES_TIME)
        
    v = []
    if options.clear_messages:
        # format = 1,2|4,5
        for xs in options.clear_messages.split('|'):
            xs = xs.split(',')
            v.append(tuple([int(x) for x in xs]))
    for t in v or settings.CLEAR_READ_MESSAGES_SCHEDULE:
        add_task('Clear read messages', gateway.clear_read_messages, t)
    return (gateway, scheduler,)

def main():
    import optparse
    
    p = optparse.OptionParser() 
    p.add_option('--port', '-p', default=None) 
    p.add_option('--clear_messages', '-c', default=None) 
    options, arguments = p.parse_args() 
    gateway, scheduler = bootstrap(options)
    
    scheduler.start()
    gateway.start()
    
    
if __name__ == "__main__":
    main()
    sys.exit(0)