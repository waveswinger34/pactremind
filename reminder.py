#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import sys
import random

from datetime import datetime
from kronos import method, ThreadedScheduler

import settings
from django.core.management import setup_environ
setup_environ(settings)

from reminder.models import Subject, IncomingMessage
from utils import MESSAGES, network, _logger

log = _logger('Reminder App')


class PACT (object):
    def __init__(self, gateway, scheduler):
        self.gateway = gateway
        self.scheduler = scheduler
        gateway.add_handler(self)
    
    def handle_sms(self, message):
        IncomingMessage(text=message.text,
                        sender=message.sender, 
                        received_at=message.received,
                        network=network(message.sender)).save()
        try:
            subject = Subject.objects.get(phone_number=message.sender)
        except:
            subject = None
        
        if not subject:
            self.register(message.sender, message.received)
        elif subject.active and message.text.lower().startswith('stop'):
            self.deactivate(subject)
        else:
            self.send(message.sender, 
                      ('You are already registered. '
                       'To stop receiving messages, text STOP. Thanks.'))
    
    def handle_call(self, modem_id, caller, dt):
        print 'We received a call on %s from %s at %s' % (modem_id, caller, dt)
        try:
            subject = Subject.objects.get(phone_number=caller)
        except:
            self.register(caller, dt)
    
    def handle_ussd_response(self, modem_id, response, code, dcs):
        print '>>> USSD RESPONSE (%s): %s' % (modem_id, response)
    
    def send(self, *args, **kwargs): 
        self.gateway.send(*args, **kwargs)
        
    def register(self, phone_number, received_at=datetime.now()):
        subject = Subject(phone_number=phone_number,
                          received_at=received_at,
                          messages_left=6)
        subject.message_id = random.randint(0, len(MESSAGES) - 1)
        subject.save()            
        self.send(phone_number, 
                  'Thanks for registering for Mobile Health Information.')
        today = datetime.today()
        cutoff = datetime(today.year, today.month, today.day, 15)
        if received_at < cutoff: # and subject.message_id:
            now  = datetime.now()
            def send_reminder_in_15():
                log.debug('Sending out task scheduled at: %s' % now)
                self.send_reminder(subject)
            self.scheduler.add_single_task(action=send_reminder_in_15,
                                           initialdelay=900, # 15 * 60 secs
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
        subjects = Subject.objects.filter(active=True).\
                                   filter(messages_left__isnull=False).\
                                   filter(messages_left__gt=0)
        for subject in subjects:
            self.send_reminder(subject)
        log.debug('Done sending reminders.')
            
    def send_final_messages(self):
        log.debug('Sending final mesasge ...')
        final_msg = 'Remember to eat lots of fruits and vegetables!'
        subjects = Subject.objects.filter(active=True).\
                                   filter(messages_left=0)
        today = datetime.today()
        subjects = [x for x in subjects if (today - x.received_at).days == 5]
        for subject in subjects:                           
            self.deactivate(subject=subject, message=final_msg)
        log.debug('Done sending final message.') 
    
def main():
    import optparse
    
    p = optparse.OptionParser() 
    p.add_option('--port', '-p', default=None) 
    p.add_option('--clear_messages', '-c', default=None) 
    options, arguments = p.parse_args() 
    
    modems, gateway = bootstrap(options)
    scheduler = setup_app(gateway, options)
    gateway.start()
    scheduler.start()
    
    
def setup_app(gateway, options):
    scheduler = ThreadedScheduler()
    app = PACT(gateway, scheduler)
    
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
    return scheduler

    

from smsapp.gsm import Modem
from smsapp.gsm import Gateway

def bootstrap(options):
    logger = Modem.debug_logger
    modems = connect_modems(options)
    gateway = Gateway(modems)
    return (modems, gateway,)

def connect_modems(options):
    logger = Modem.debug_logger
    d = {}
    for id, data_port, control_port in get_modems(options):
        modem = Modem(id=id,
                      port=data_port,
                      control_port=control_port,
                      logger=logger).boot()
        d.update({id:modem})
    return d

def get_modems(options, id1='Airtel', id2='MTN'):
    import re
    import os
    modems = [(id1,
               '/dev/cu.HUAWEIMobile-Modem',
               '/dev/cu.HUAWEIMobile-Pcui',)]
    xs = ['/dev/%s' % x for x in os.listdir('/dev/') \
          if re.match(r'cu.HUAWEI.*-\d+', x)][:2]
    if xs:
        modems.append((id2, xs[0], xs[1]))
    return modems
    
if __name__ == "__main__":
    main()
    sys.exit(0)