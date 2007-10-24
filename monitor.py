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
import itertools
import getopt
import socket
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

        self.logname = logname
        if self.logname:
            self.log = open(self.logname, "a")
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
        mgr = manager(level=manager.LOG_ERROR, log_file=self.log)
        return mgr.runWithOptions(
            self.minfo.serverinfo,
            "",
            [script,],
            {
                "$userid1:"   : self.user,
                "$pswd1:"     : self.pswd,
                "$principal1:": "/principals/users/%s/" % (self.user,)
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
        try:
            sendemail(
                fromaddr = ("Do Not Reply", self.minfo.notify_from),
                toaddrs = [("", a) for a in self.minfo.notify],
                subject = self.minfo.notify_subject,
                body = self.minfo.notify_body % (msg,),
            )
        except Exception, e:
            self.doError(str(e))

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
            if result != 0:
                msg = "WARNING: request failed"
                self.logtxt(msg)
                if self.minfo.notify_request_failed and (time.time() - last_notify > self.minfo.notify_interval * 60):
                    self.logtxt("Sending notification to %s" % (self.minfo.notify,))
                    self.doNotification(msg)
                    last_notify = time.time()
            elif timing >= self.minfo.warningtime:
                msg = "WARNING: request time (%.3f) exceeds limit (%.3f)" % (timing, self.minfo.warningtime,)
                self.logtxt(msg)
                if self.minfo.notify_time_exceeded and (time.time() - last_notify > self.minfo.notify_interval * 60):
                    self.logtxt("Sending notification to %s" % (self.minfo.notify,))
                    self.doNotification(msg)
                    last_notify = time.time()

    @staticmethod
    def reportStart(html):
        nowstr = str(datetime.datetime.now().replace(microsecond=0))
        if html:
            print """<html>
<head><title>Server Status</title></head>
<body>
<h2>Server Status on %s</h2>
""" % (nowstr,)
        else:
            print """Server Status on %s

""" % (nowstr,)

    @staticmethod
    def reportEnd(html):
        if html:
            print """
</body>
</html>
"""

    def reportUptime(self, html):
        
        # Read in the logfile and count failures.
        startstops = []
        failures = 0
        last_failure = None
        fd = open(self.logname, "r")
        for line in fd:
            if line.find("Starting Monitor") != -1:
                startstops.append(line)
            elif line.find("Stopped Monitor") != -1:
                startstops.append(line)
            elif line.find("WARNING: request failed") != -1:
                failures += 1
                last_failure = line
        
        # Failed time = number of failures * monitor period (seconds)
        downtime = int(failures * self.minfo.period)
        
        # Now calculate actual monitor run time
        elapsed_time = 0
        start = None
        firststart = None
        for item in startstops:
            if start is None and item.find("Starting Monitor") != -1:
                start = self.parse_date(item)
                if firststart is None:
                    firststart = self.parse_date(item)
            elif start is not None and item.find("Stopped Monitor"):
                end = self.parse_date(item)
                delta = end - start
                elapsed_time += delta.days * 24 * 60 * 60 + delta.seconds
                start = None
        
        if start is not None:
            end = datetime.datetime.now()
            delta = end - start
            elapsed_time += delta.days * 24 * 60 * 60 + delta.seconds
        
        uptime = elapsed_time - downtime

        # Determine whether its up or down right now
        if last_failure:
            lastdowntime = self.parse_date(last_failure)
            now = datetime.datetime.now()
            diff = now - lastdowntime
            diff = diff.days * 24 * 60 * 60 + diff.seconds
            if diff < 2 * self.minfo.period:
                status = "DOWN"
            else:
                status = "UP"
        else:
            status = "UP"
        if html:
            print """
<h3>Server: %s</h3>
<table>
<tr><td>Since</td><td>%s</td></tr>
<tr><td>Uptime</td><td>approx. %d (hours) / %d (days)</td></tr>
<tr><td>Downtime</td><td>approx. %d (minutes) / %d (hours)</td></tr>
<tr><td>Percentage</td><td>%.3f%%</td></tr>
<tr><td>&nbsp;</td><td>&nbsp;<td></tr>
<tr><td>Current Status</td><td>%s<td></tr>
</table>

""" % (self.minfo.name, str(firststart), uptime/60/60, uptime/60/60/24, downtime/60, downtime/60/60, ((uptime - downtime) * 100.0)/uptime, status)
        else:
            print """
Server: %s
    Since:      %s
    Uptime:     approx. %d (hours) / %d (days)
    Downtime:   approx. %d (minutes) / %d (hours)
    Percentage: %.3f%%

    Current Status: %s

""" % (self.minfo.name, str(firststart), uptime/60/60, uptime/60/60/24, downtime/60, downtime/60/60, ((uptime - downtime) * 100.0)/uptime, status)

    def parse_date(self, line):
        
        date = line[1:].split(']')[0]
        return datetime.datetime(*(time.strptime(date, "%Y-%m-%d %H:%M:%S")[0:6]))

def usage():
    print """Usage: monitor.py [options] [<configfile>] [<logfile>]
Options:
    -h       Print this help and exit
    -u       generate report of server uptime
    --html   generate report as HTML
"""

if __name__ == "__main__":
    
    infoname = "scripts/monitoring/monitorinfo.xml"
    uptime = False
    html = False

    options, args = getopt.getopt(sys.argv[1:], "huw", ["html"])

    for option, value in options:
        if option == "-h":
            usage()
            sys.exit(0)
        elif option == "-u":
            uptime = True
        elif option == "--html":
            html = True
        else:
            print "Unrecognized option: %s" % (option,)
            usage()
            raise ValueError

    if uptime:
        infoname = []
        logname = []
        for i in range(len(args)/2):
            infoname.append(args[2 * i])
            logname.append(args[2 * i + 1])

    else:
        if len(args) > 0:
            infoname = args[0]
            
        if len(args) > 1:
            logname = args[1]
        else:
            logname = None

    if uptime:
        user = ""
        pswd = ""
    else:
        user = "cdaboo" #raw_input("User: ")
        pswd = "caldav6585-2" #getpass("Password: ")
    
    if uptime:
        monitor.reportStart(html)
        for info, log in itertools.izip(infoname, logname):
            m = monitor(info, log, user, pswd)
            m.readXML()
            m.reportUptime(html)
        monitor.reportEnd(html)
    else:
        m = monitor(infoname, logname, user, pswd)
        m.readXML()

        def signalEnd(sig, frame):
            m.doEnd()
            sys.exit()
    
        signal.signal(signal.SIGINT, signalEnd)
        socket.setdefaulttimeout(m.minfo.timeout)
    
        m.doStart()
    
        try:
            m.runLoop()
        except SystemExit:
            pass
        except Exception, e:
            m.doError(str(e))
