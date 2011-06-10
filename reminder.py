#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


import logging
import traceback
import time
from kronos import method, ThreadedScheduler
from utils import *

from pygsm import GsmModem

log = logging.getLogger("Reminder")


class Gateway:
    """The Gateway itself."""

    def __init__(self, modem):
        self.running = True
        self.thread = None
        
#    def __init__(self, modem, scheduler):
        self.register = {}
        self.count = 0
        self.modem = modem
#        self.scheduler = scheduler

    def _acquire_lock(self):
        pass

    def _release_lock(self):
        pass

    def handle(self, msg):
        # check if sender in database
        if msg.sender not in self.register:
            #self.register.append(msg)
            self.register[msg.sender] = msg
            self.send(msg.sender, "Thanks for registering.")
            
#            if self.count % 2 is 0:
#                self.scheduler.add(msg)
#            self.count += 1
        elif msg.text.lower() is 'stop':
            print 'OK OK we get it!'
            #TODO
        else:
            msg.respond(('You are already registered. '
                         'To stop receiving messages, text STOP. Thanks'))    

    def send(self, number, msg):
        self.modem.send_sms(number, msg)
        return self.modem.wait_for_network()

    def start(self):
        """Start the gateway."""
        self._run()

    def stop(self):
        """Remove all pending tasks and stop the Gateway."""
        self.running = False

    def _run(self):
        # Low-level run method to do the actual scheduling loop.
        while self.running:
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
            # queue is empty; sleep a short while before checking again
#                self.modem.wait_for_network()
            if self.running:
                time.sleep(2)


try:
    import threading

    class ThreadedGateway(Gateway):
        """A Gateway that runs in its own thread."""

        def __init__(self, modem):
            Gateway.__init__(self, modem)
            # we require a lock around the task queue
            self._lock = threading.Lock()

        def start(self):
            """Splice off a thread in which the gateway will run."""
            self.thread = threading.Thread(target=self._run)
#            self.thread.setDaemon(True)
            self.thread.start()
            
        def stop(self):
            """Stop the gateway and wait for the thread to finish."""
            print '>>> Stopping '
            Gateway.stop(self)
            try:
                self.thread.join()
            except AttributeError:
                pass

        def _acquire_lock(self):
            """Lock the thread's task queue."""
            self._lock.acquire()
            
        def _release_lock(self):
            """Release the lock on th ethread's task queue."""
            self._lock.release()

except ImportError:
    # threading is not available
    pass


class Server(object):
    modem = None
    
    def handle(self, msg):
        pass
    
    def listen(self):
        while True:
            print "Checking for message..."
            msg = self.modem.next_message()

            if msg is not None:
                self.handle(msg)
            time.sleep(2)


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


subjects = [('0266688206', 0, 6), ('0548315007', 1, 6), ('0245206514', 2, 6)]
#
def broadcast(gateway):
    print 'Broadcasting ...'
    
    for subject in subjects:
        text = MESSAGES[subject[1]]
        print '>>> sending info: %s' % text
        gateway.send(number=subject[0], msg=text)
#        subject.messages_left -= 1
#        subject.save()
        print ">>  message sent: %s" % subject
#
#class DemoServer(Server):
#    def __init__(self, modem):
#        self.modem = modem
#    
##    def listen(self):
##        super(Server, self).listen()
##        self._run()
##        
#    def _run(self):
#        
#        import random
#        for i in range(0, 3):
#            for number in ['0263119161', '0245014728']:
#                msg = 'Hello %s' % random.randint(0, 100)
#                print 'Sending %s to %s' % (msg, number)
#                self.send(number, msg)


def main():
    port = '/dev/tty.HUAWEIMobile-Modem'
    logger = GsmModem.debug_logger
    modem = GsmModem(port=port, logger=logger).boot()
    
    print "Waiting for network..."
    tmp = modem.wait_for_network()
    
    # listen the demo app
    gateway = Gateway(modem)
    
#    d = DemoServer(gsm)
#    d.listen()
#    d._run()
    
    #gsm.send_sms('0245014728', 'Hello')
    #gsm.wait_for_network()
    #gsm.send_sms('0245014728', 'wohoo')

    print "Listener setup"

    scheduler = ThreadedScheduler()
    tx = [(17,19), (17, 20)]
    for i in range(len(tx)):
        scheduler.add_daytime_task(action=broadcast, 
                               taskname="Action %s" % i, 
                               weekdays=range(1,8),
                               monthdays=None, 
                               processmethod=method.threaded, 
                               timeonday=tx[i],
                               args=[gateway], kw=None)
    scheduler.start()
    gateway.start()
    
#    print "Scheduler started, waiting 15 sec...."
#    time.sleep(15)
#    
#    print "STOP SCHEDULER"
#    sched.stop()

#    print "EXITING"
    
    
if __name__ == "__main__":
    import sys
    main()
    sys.exit(0)
    






