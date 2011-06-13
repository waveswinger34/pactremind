from pygsm import GsmModem
import re

class Modem(GsmModem):

    def clear_read_messages(self, debug=False):
        
        s = self.query('AT+CMGD=?')
        if "error" in s.lower():
            print "Error - phone not supported"
        else:
            if debug:
                #+CMGD: (0,1),(0-4)
                print s
            match = re.search(r'\+CMGD: \(([^\)]+)\),\((\d)-(\d)\)', s)
            if match:
                xs = [int(x) for x in match.group(1).split(',')]
#                n = int(match.group(1))
                if debug:
                    print 'To delete is: %s' % xs
                for i in xs:
                    try:
                        temp = self.command('AT+CMGR=' + str(i+1)+',1')
                        if "REC READ" in temp[0]:
                            self.query('AT+CMGD=' + str(i+1))
                    except: pass