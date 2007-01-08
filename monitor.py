#!/usr/bin/env python
#
##
# Copyright (c) 2006 Apple Computer, Inc. All rights reserved.
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
import signal
import time
import datetime
import sys

import xml.dom.minidom
import src.xmlDefs

from src.manager import manager
from src.monitorinfo import monitorinfo

EX_INVALID_CONFIG_FILE = "Invalid Config File"

if __name__ == "__main__":
    
    def readXML():

        monitorinfoname = "scripts/monitoring/monitorinfo.xml"
        if len(sys.argv) > 1:
            monitorinfoname = sys.argv[1]
            
        # Open and parse the server config file
        fd = open(monitorinfoname, "r")
        doc = xml.dom.minidom.parse( fd )
        fd.close()

        # Verify that top-level element is correct
        monitorinfoname_node = doc._get_documentElement()
        if monitorinfoname_node._get_localName() != src.xmlDefs.ELEMENT_MONITORINFO:
            raise EX_INVALID_CONFIG_FILE
        if not monitorinfoname_node.hasChildNodes():
            raise EX_INVALID_CONFIG_FILE
        minfo = monitorinfo()
        minfo.parseXML(monitorinfoname_node)
        return minfo
    
    minfo = readXML()

    def doScript(script, dict={}):
        mgr = manager(level=manager.LOG_NONE)
        return mgr.runWithOptions(minfo.serverinfo, "", [script,], dict)

    def doStart():
        if minfo.startscript:
            print "Runnning start script %s" % (minfo.startscript,)
            doScript(minfo.startscript)

    def doEnd(sig, frame):
        if minfo.endscript:
            print "Runnning end script %s" % (minfo.endscript,)
            doScript(minfo.endscript)
        sys.exit()

    signal.signal(signal.SIGINT, doEnd)

    doStart()

    if minfo.logging:
        print "Start:"
    try:
        while(True):
            time.sleep(minfo.period)
            result, timing = doScript(minfo.testinfo, minfo.subsdict)
            if minfo.logging:
                print "Result: %d, Timing: %.3f" % (result, timing,)
            if timing >= minfo.warningtime:
                print "[%s] WARNING: request time (%.3f) exceeds limit (%.3f)" % (str(datetime.datetime.now()), timing, minfo.warningtime,)
            if result != 0:
                print "[%s] WARNING: request failed" % (str(datetime.datetime.now()),)
        if minfo.logging:
            print "Done"
    except SystemExit:
        pass
    except Exception, e:
        print "Run exception: %s" % (str(e),)
