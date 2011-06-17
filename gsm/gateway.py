import sys
import time
import traceback

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
        print 'Sending: %s' % text
        self.modem.send_sms(number, text)
        s = self.modem.wait_for_network()
        return s
    
    def clear_read_messages(self):
        self.poll = False
        self.modem.clear_read_messages(True)
        self.poll = True
        
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
                    print 'Checking for next message...'
                    message = self.modem.next_message()
                    if message is not None:
                        self.app.handle(message)
                except KeyboardInterrupt:
                    print 'Ctrl-c received! Sending kill signal ...'
                    self.stop()
                except Exception, x:
                    print >>sys.stderr, "ERROR DURING GATEWAY EXECUTION", x
                    print >>sys.stderr, "".join(
                        traceback.format_exception(*sys.exc_info()))
                    print >>sys.stderr, "-" * 20
            if self.running:
                time.sleep(self.interval)