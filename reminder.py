#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import sys
import random
import time

from datetime import datetime
from kronos import method, ThreadedScheduler

import settings
from django.core.management import setup_environ
setup_environ(settings)
from reminder.models import Subject, IncomingMessage

from utils import _logger

from simplesms import Handler
from simplesms.contrib.gh import network
from simplesms.contrib.gh import sanitize_number

log = _logger('Reminder App')


class PACT (Handler):
    def __init__(self, gateway, scheduler):
        self.scheduler = scheduler
        Handler.__init__(self, gateway)
    
    def handle_sms(self, message):
        phone_number = sanitize_number(message.sender)
        IncomingMessage(text=message.text,
                        sender=phone_number, 
                        received_at=message.received,
                        network=network(message.sender)).save()
        try:
            subject = Subject.objects.get(phone_number=phone_number)
        except:
            subject = None
        
        if not subject:
            self.register(phone_number, message.received)
        elif subject.active and message.text.lower().startswith('stop'):
            self.deactivate(subject)
        else:
            self.send(message.sender, 
                      settings.ALREADY_REGISTERED_MESSAGE)
    
    def handle_call(self, modem_id, caller, dt):
        phone_number = sanitize_number(caller)
        try:
            subject = Subject.objects.get(phone_number=phone_number)
        except:
            self.register(phone_number, dt)
    
    def register(self, phone_number, received_at=datetime.now()):
        if not phone_number.startswith('+'):
            phone_number = sanitize_number(phone_number)
        subject = Subject(phone_number=phone_number,
                          received_at=received_at,
                          messages_left=6)
        if len(Subject.objects.all()) % 2 ==0: #new
            subject.message_id = random.randint(0, 
                                                len(settings.MESSAGES) - 1)
        subject.save()            
        self.send(phone_number, 
                  settings.REGISTRATION_SUCCESS_MESSAGE)
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
            text = settings.MESSAGES[subject.message_id]
            log.debug('>>> sending info: %s' % text)
            self.send(number=subject.phone_number, text=text)
            subject.messages_left -= 1
            subject.save()
            log.debug(">>  message sent: %s" % subject)
        else:
            log.debug('>> %s has no reminders left' % subject)

    def deactivate(self, subject, 
                   message=settings.DEFAULT_DEACTIVATION_MESSAGE):
        subject.active = False
        subject.save()
        if message:
            self.send(subject.phone_number, message)
    
    def send_reminders(self):
        log.debug('Sending reminders ...')
        subjects = Subject.objects.filter(active=True).\
                                   filter(message_id__isnull=False).\
                                   filter(messages_left__gt=0)
        for subject in [x for x in subjects if x.message_id is not None]:
            self.send_reminder(subject)
        log.debug('Done sending reminders.')
            
    def send_final_messages(self):
        log.debug('Sending final mesasge ...')
        #subjects = Subject.objects.filter(active=True).\
                                   #filter(messages_left=0)
        subjects = Subject.objects.filter(active=True)
        today = datetime.today()
        subjects = [x for x in subjects if (today - x.received_at).days == 2]
        for subject in subjects: 
            self.send(subject.phone_number, 
                      settings.FINAL_MESSAGE)                       
        log.debug('Done sending final message.') 
    
def main():
    import optparse
    
    p = optparse.OptionParser() 
    p.add_option('--port', '-p', default=None) 
    p.add_option('--clear-messages', '-c', action='store_true', 
                 dest='clear_messages', default=False) 
    p.add_option('--clear-schedule', '-x', dest='clear_schedule', default=None) 
    options, arguments = p.parse_args() 
    
    modems, gateway = bootstrap(options)
    scheduler = setup_app(gateway, options)
    gateway.start(clear_messages=options.clear_messages)
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
    if options.clear_schedule:
        # format = 1,2|4,5
        for xs in options.clear_schedule.split('|'):
            xs = xs.split(',')
            v.append(tuple([int(x) for x in xs]))
    for t in v or settings.CLEAR_READ_MESSAGES_SCHEDULE:
        add_task('Clear read messages', gateway.clear_read_messages, t)
    return scheduler

    

from simplesms import Modem
from simplesms import Gateway
from pygsm import errors

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
                      logger=logger)
        modem = modem.boot()
#        try:
#        except errors.GsmModemError:
#            modem.connect()
#            modem.command('AT+CFUN=0')
#            time.sleep(4)
#            modem.init()
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