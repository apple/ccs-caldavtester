#!/usr/bin/env python
#
##
# Copyright (c) 2006-2007 Apple Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# DRI: Cyrus Daboo, cdaboo@apple.com
##
#
# Runs a series of test suites inb parallel using a thread pool
#

from getpass import getpass
import datetime
import signal
import sys
import time
import xml.dom.minidom

from src.sendemail import sendemail
from src.manager import manager
from src.monitorinfo import monitorinfo
import src.xmlDefs

EX_INVALID_CONFIG_FILE = "Invalid Config File"

class monitor(object):
    
    def __init__(self, infoname, logname, user, pswd):
        self.infoname = infoname
        self.user = user
        self.pswd = pswd
        self.minfo = None

        if logname:
            self.log = open(logname, "a")
        else:
            self.log = None
            
        self.running = True

    def readXML(self):

        # Open and parse the server config file
        fd = open(self.infoname, "r")
        doc = xml.dom.minidom.parse( fd )
        fd.close()

        # Verify that top-level element is correct
        node = doc._get_documentElement()
        if node._get_localName() != src.xmlDefs.ELEMENT_MONITORINFO:
            raise EX_INVALID_CONFIG_FILE
        if not node.hasChildNodes():
            raise EX_INVALID_CONFIG_FILE
        self.minfo = monitorinfo()
        self.minfo.parseXML(node)
    
    def doScript(self, script):
        mgr = manager(level=manager.LOG_NONE)
        return mgr.runWithOptions(
            self.minfo.serverinfo,
            "",
            [script,],
            {
                "$userid1:"  : self.user,
                "$pswd1:"    : self.pswd,
                "$principal:": "/principals/users/%s/" % (self.user,)
            }
        )

    def doStart(self):
        self.logtxt("Starting Monitor")

        if self.minfo.startscript:
            self.logtxt("Runnning start script %s" % (self.minfo.startscript,))
            self.doScript(self.minfo.startscript)

    def doEnd(self):
        if self.minfo.endscript:
            self.logtxt("Runnning end script %s" % (self.minfo.endscript,))
            self.doScript(self.minfo.endscript)

        self.logtxt("Stopped Monitor")
        self.running = False

    def doError(self, msg):
        self.logtxt("Run exception: %s" % (msg,))

    def doNotification(self, msg):
        sendemail(
            fromaddr = ("Do Not Reply", self.minfo.notify_from),
            toaddrs = [("", a) for a in self.minfo.notify],
            subject = self.minfo.notify_subject,
            body = self.minfo.notify_body % (msg,),
        )

    def logtxt(self, txt):
        dt = str(datetime.datetime.now())
        dt = dt[0:dt.rfind(".")]
        if self.log:
            self.log.write("[%s] %s\n" % (dt, txt,))
            self.log.flush()
        else:
            print "[%s] %s" % (dt, txt,)
    
    def runLoop(self):
        last_notify = 0
        while(self.running):
            time.sleep(self.minfo.period)
            if not self.running:
                break
            result, timing = m.doScript(self.minfo.testinfo)
            if not self.running:
                break
            if self.minfo.logging:
                self.logtxt("Result: %d, Timing: %.3f" % (result, timing,))
            if timing >= self.minfo.warningtime:
                msg = "WARNING: request time (%.3f) exceeds limit (%.3f)" % (timing, self.minfo.warningtime,)
                self.logtxt(msg)
                if self.minfo.notify_time_exceeded and (time.time() - last_notify > self.minfo.notify_interval * 60):
                    self.logtxt("Sending notification to %s" % (self.minfo.notify,))
                    self.doNotification(msg)
                    last_notify = time.time()
            if result != 0:
                msg = "WARNING: request failed"
                self.logtxt(msg)
                if self.minfo.notify_request_failed and (time.time() - last_notify > self.minfo.notify_interval * 60):
                    self.logtxt("Sending notification to %s" % (self.minfo.notify,))
                    self.doNotification(msg)
                    last_notify = time.time()

if __name__ == "__main__":
    
    infoname = "scripts/monitoring/monitorinfo.xml"
    if len(sys.argv) > 1:
        infoname = sys.argv[1]
        
    if len(sys.argv) > 2:
        logname = sys.argv[2]
    else:
        logname = None

    user = raw_input("User: ")
    pswd = getpass("Password: ")
    
    m = monitor(infoname, logname, user, pswd)
    m.readXML()

    def signalEnd(sig, frame):
        m.doEnd()
        sys.exit()

    signal.signal(signal.SIGINT, signalEnd)

    m.doStart()

    try:
        m.runLoop()
    except SystemExit:
        pass
    except Exception, e:
        m.doError(str(e))
