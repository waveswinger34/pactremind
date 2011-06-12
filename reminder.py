#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


import logging
import traceback
import random
import time
from kronos import method, ThreadedScheduler
from utils import *

import settings
from django.core.management import setup_environ

setup_environ(settings)

from reminder.models import *

from pygsm import GsmModem

log = logging.getLogger("Reminder")



class Gateway:
    """The Gateway itself."""

    def __init__(self, modem, interval=2):
        self.running = True
        self.poll = True
        self.thread = None
        self.register = {}
        self.count = 0
        self.modem = modem
        self.interval = interval

    def _acquire_lock(self):
        pass

    def _release_lock(self):
        pass

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
            
            txt = "Thanks for registering."
            self.send(msg.sender, txt)
        elif msg.text.lower() is 'stop' and subject.active:
            subject.active = False
            subject.save()
            msg.response('You have been removed from PACT')
        else:
            txt = ("You are already registered. "
                   "To stop receiving messages, text STOP. Thanks.")
            print txt

    def send(self, number, msg):
        self.modem.send_sms(number, msg)
        s = self.modem.wait_for_network()
        return s
        
    def start(self):
        """Start the gateway."""
        self._run()

    def stop(self):
        """Remove all pending tasks and stop the Gateway."""
        self.running = False

    def _run(self):
        # Low-level run method to do the actual scheduling loop.
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
                # queue is empty; sleep a short while before checking again
    #                self.modem.wait_for_network()
            if self.running:
                time.sleep(self.interval)


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


subjects = [('0266688206', 0, 6)]
#
def broadcast(gateway):
    print 'Broadcasting ...'
    gateway.poll = False
    for subject in subjects:
        text = MESSAGES[subject[1]]
        print '>>> sending info: %s' % text
        
        gateway.send(number=subject[0], msg=text)
#        subject.messages_left -= 1
#        subject.save()
        print ">>  message sent: %s" % subject[0]
    gateway.poll = True
#

def main():
    port = '/dev/tty.HUAWEIMobile-Modem'
    logger = GsmModem.debug_logger
    modem = GsmModem(port=port, logger=logger).boot()
    
    print "Waiting for network..."
    tmp = modem.wait_for_network()
    
    # listen the demo app
    gateway = Gateway(modem)
    
    print "Listener setup"

    scheduler = ThreadedScheduler()
    tx = [(05,58), (05, 59)]
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
    
    
if __name__ == "__main__":
    import sys
    main()
    sys.exit(0)
    






