#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import time
from pygsm import GsmModem

class Server(object):
    modem = None
    
    def handle(self, msg):
        pass
    
    def send(self, number, msg):
        self.modem.send_sms(number, msg)
        self.modem.wait_for_network()
          
    def start(self):
        while True:
            print "Checking for message..."
            msg = self.modem.next_message()

            if msg is not None:
                self.handle(msg)
            time.sleep(2)


class Reminder(Server):
    def __init__(self, modem, scheduler):
        self.register = {}
        self.count = 0
        self.modem = modem
        self.scheduler = scheduler

    def handle(self, msg):
        # check if sender in database
        if msg.sender not in self.register:
            #self.register.append(msg)
            self.register[msg.sender] = msg
            #msg.respond("Thanks for registering.")
            self.send(msg.sender, "Thanks for registering.")
            
            if self.count % 2 is 0:
                self.scheduler.add(msg)
            self.count += 1
        elif msg.text.lower() is 'stop':
            print 'OK OK we get it!'
            #TODO
        else:
            msg.respond("You are already registered. To stop receiving messages, text STOP. Thanks")    


class Scheduler(object):
    
    def __init__(self, modem):
        self.q = []
        self.modem = modem
    
    def poll(self):
        pass
    
    def add(self, msg):
        if int(msg._rawtime.split(':')[0]) < 17:
            self.modem.send_sms(msg.sender, 'Reminder to take meds')
            self.modem.wait_for_network()
            self.q.append((msg.sender, 5))
        else:
            self.q.append((msg.sender, 6))


import logging
log = logging.getLogger('Demo Server')
class DemoServer(Server):
    def __init__(self, modem):
        self.modem = modem
    
#    def start(self):
#        super(Server, self).start()
#        self._run()
#        
    def _run(self):
        
        import random
        for i in range(0, 3):
            for number in ['0263119161', '0245014728']:
                msg = 'Hello %s' % random.randint(0, 100)
                log.debug('Sending %s to %s' % (msg, number))
                self.send(number, msg)


def main():
    port = '/dev/tty.airtel'
    logger = GsmModem.debug_logger
    gsm = GsmModem(port=port, logger=logger).boot()
    
    print "Waiting for network..."
    s = gsm.wait_for_network()
    
    # start the demo app
#    app = Reminder(gsm, Scheduler(gsm))
#    app.serve()
    
    d = DemoServer(gsm)
    #d.start()
    d._run()
    
    #gsm.send_sms('0245014728', 'Hello')
    #gsm.wait_for_network()
    #gsm.send_sms('0245014728', 'wohoo')
    
if __name__ == "__main__":
    import sys
    main()
    sys.exit(0)