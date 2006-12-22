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
import sys

from random import randrange
from threading import Timer
import math
import time
import xml.dom.minidom
import src.xmlDefs

from src.manager import manager
from src.perfinfo import perfinfo

EX_INVALID_CONFIG_FILE = "Invalid Config File"
START_DELAY = 3.0

if __name__ == "__main__":
    
    def readXML():

        perfinfoname = "scripts/performance/perfinfo.xml"
        if len(sys.argv) > 1:
            perfinfoname = sys.argv[1]
            
        # Open and parse the server config file
        fd = open(perfinfoname, "r")
        doc = xml.dom.minidom.parse( fd )
        fd.close()

        # Verify that top-level element is correct
        perfinfo_node = doc._get_documentElement()
        if perfinfo_node._get_localName() != src.xmlDefs.ELEMENT_PERFINFO:
            raise EX_INVALID_CONFIG_FILE
        if not perfinfo_node.hasChildNodes():
            raise EX_INVALID_CONFIG_FILE
        pinfo = perfinfo()
        pinfo.parseXML(perfinfo_node)
        return pinfo
    
    def subs(str, i):
        if "%" in str:
            return str % i
        else:
            return str

    pinfo = readXML()

    def doScript(script):
        # Create argument list that varies for each threaded client. Basically use a separate
        # server account for each client.
        def runner(*args):
            """
            Test runner method. 
            @param *args:
            """
            
            if pinfo.logging:
                print "Start: %s" % (args[0]["moresubs"]["$userid1:"],)
            try:
                mgr = manager(level=manager.LOG_NONE)
                result, timing = mgr.runWithOptions(*args[1:], **args[0])
                if pinfo.logging:
                    print "Done: %s" % (args[0]["moresubs"]["$userid1:"],)
            except Exception, e:
                print "Thread run exception: %s" % (str(e),)
    
        args = []
        for i in range(1, pinfo.clients + 1):
            moresubs = {}
            for key, value in pinfo.subsdict.iteritems():
                moresubs[key] = subs(value, i)
            args.append(({"moresubs": moresubs}, subs(pinfo.serverinfo, i), "", [subs(script, i)]))
        for arg in args:
            runner(*arg)

    def doStart():
        if pinfo.startscript:
            print "Runnning start script %s" % (pinfo.startscript,)
            doScript(pinfo.startscript)

    def doEnd():
        if pinfo.endscript:
            print "Runnning end script %s" % (pinfo.endscript,)
            doScript(pinfo.endscript)

    doStart()

    # Cummulative results
    allresults = []
    
    for test in pinfo.tests:
        result = [0.0, 0.0, 0.0]
        print "|",
        for loop in range(test[2]):
            print ".",
            results = []
        
            def runner(*args):
                """
                Test runner method. 
                @param *args:
                """
                
                if pinfo.logging:
                    print "Start: %s" % (args[0]["moresubs"]["$userid1:"],)
                try:
                    mgr = manager(level=manager.LOG_NONE)
                    result, timing = mgr.runWithOptions(*args[1:], **args[0])
                    results.append(timing)
                    if pinfo.logging:
                        print "Done: %s" % (args[0]["moresubs"]["$userid1:"],)
                except Exception, e:
                    print "Thread run exception: %s" % (str(e),)
        
            # Create argument list that varies for each threaded client. Basically use a separate
            # server account for each client.
            args = []
            for i in range(1, test[0] + 1):
                moresubs = {}
                for key, value in pinfo.subsdict.iteritems():
                    moresubs[key] = subs(value, i)
                args.append(({"moresubs": moresubs}, subs(pinfo.serverinfo, i), "", [subs(pinfo.testinfo, i)]))
        
            if pinfo.threads:
                # Run threads by queuing up a set of timers set to start 5 seconds + random time
                # after thread is actually started. The random time is spread over the interval
                # we are testing over. Wait for all threads to finish.
                timers = []
                for arg in args:
                    sleeper = START_DELAY + randrange(0, 100)/100.0 * test[1]
                    timers.append(Timer(sleeper, runner, arg))
            
                startTime = time.time() + START_DELAY
                for thread in timers:
                    thread.start( )
            
                for thread in timers:
                    thread.join(None)
            else:
                # Just execute each client request one after the other.
                startTime = time.time()
                for arg in args:
                    runner(*arg)
    
            # Determine timing stats for this run
            diffTime = time.time() - startTime

            average = 0.0
            for i in results:
                average += i
                if pinfo.logging:
                    print i
            average /= len(results)
            
            stddev = 0.0
            for i in results:
                stddev += (i - average) ** 2
            stddev /= len(results)
            stddev = math.sqrt(stddev)
            
            result[0] += average
            result[1] += stddev
            result[2] += diffTime
        
        # Average results from runs.
        result[0] /= test[2]
        result[1] /= test[2]
        result[2] /= test[2]
        
        allresults.append(result)
    
    doEnd()

    # Print out averaged results.
    print "\n\nClients\tSpread\tReqs/sec\tAverage\t\tStd. Dev.\tTotal"
    print "==============================================================="
    for i in range(len(pinfo.tests)):
        print "%.0f\t%.0f\t%.3f\t\t%.3f\t\t%.3f\t\t%.3f" % (pinfo.tests[i][0], pinfo.tests[i][1], pinfo.tests[i][0]/pinfo.tests[i][1], allresults[i][0], allresults[i][1], allresults[i][2],)
