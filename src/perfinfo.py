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
##
from src.manager import manager
from random import randrange
from threading import Timer
import time

"""
Class that encapsulates the server information for a CalDAV test run.
"""

import src.xmlDefs
import xml.dom.minidom

START_DELAY = 3.0

class perfinfo( object ):
    """
    Maintains information about the performance test scenario.
    """
    __slots__  = ['clients', 'threads', 'logging', 'tests', 'serverinfo', 'startscript', 'testinfo', 'endscript', 'subsdict']

    def __init__( self ):
        self.clients = 20
        self.threads = True
        self.logging = False
        self.tests = []
        self.serverinfo = ""
        self.startscript = ""
        self.testinfo = ""
        self.endscript = ""
        self.subsdict = {}

    @classmethod
    def runIt(cls, type, script, silent=False, offset=0):
    
        if type not in ("load ramping",):
            raise ValueError("Performance type '%s' not supported." % (type,))

        pinfo = perfinfo.parseFile(script)
    
        pinfo.doStart(silent)
    
        if type == "load ramping":
            allresults = pinfo.doLoadRamping(offset)
    
        pinfo.doEnd(silent)
        
        return allresults
    

    @classmethod
    def parseFile(cls, filename):
        # Open and parse the server config file
        fd = open(filename, "r")
        doc = xml.dom.minidom.parse( fd )
        fd.close()
    
        # Verify that top-level element is correct
        perfinfo_node = doc._get_documentElement()
        if perfinfo_node._get_localName() != src.xmlDefs.ELEMENT_PERFINFO:
            raise ValueError("Invalid configuration file: %s" % (filename,))
        if not perfinfo_node.hasChildNodes():
            raise ValueError("Invalid configuration file: %s" % (filename,))
        pinfo = perfinfo()
        pinfo.parseXML(perfinfo_node)
        return pinfo
        
    def parseXML( self, node ):
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_CLIENTS:
                self.clients = int(child.firstChild.data)
            elif child._get_localName() == src.xmlDefs.ELEMENT_THREADS:
                self.threads = child.getAttribute( src.xmlDefs.ATTR_ENABLE ) != src.xmlDefs.ATTR_VALUE_NO
            elif child._get_localName() == src.xmlDefs.ELEMENT_LOGGING:
                self.logging = child.getAttribute( src.xmlDefs.ATTR_ENABLE ) != src.xmlDefs.ATTR_VALUE_NO
            elif child._get_localName() == src.xmlDefs.ELEMENT_TESTS:
                self.parseTestsXML(child)
            elif child._get_localName() == src.xmlDefs.ELEMENT_SERVERINFO:
                self.serverinfo = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_START:
                if child.firstChild is not None:
                    self.startscript = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_TESTINFO:
                self.testinfo = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_END:
                if child.firstChild is not None:
                    self.endscript = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_SUBSTITUTIONS:
                self.parseSubstitutionsXML(child)

    def parseTestsXML(self, node):
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_TEST:
                clients = self.clients
                spread = None
                runs = None
                for schild in child._get_childNodes():
                    if schild._get_localName() == src.xmlDefs.ELEMENT_CLIENTS:
                        clist = schild.firstChild.data.split(",")
                        if len(clist) == 1:
                            clients = int(clist[0])
                        else:
                            clients = range(int(clist[0]), int(clist[1]) + 1, int(clist[2]))
                    elif schild._get_localName() == src.xmlDefs.ELEMENT_SPREAD:
                        spread = float(schild.firstChild.data)
                    elif schild._get_localName() == src.xmlDefs.ELEMENT_RUNS:
                        runs = int(schild.firstChild.data)
                if spread and runs:
                    if isinstance(clients, list):
                        for client in clients:
                            self.tests.append((client, spread, runs,))
                    else:
                        self.tests.append((clients, spread, runs,))

    def parseSubstitutionsXML(self, node):
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_SUBSTITUTION:
                key = None
                value = None
                for schild in child._get_childNodes():
                    if schild._get_localName() == src.xmlDefs.ELEMENT_KEY:
                        key = schild.firstChild.data
                    elif schild._get_localName() == src.xmlDefs.ELEMENT_VALUE:
                        value = schild.firstChild.data
                if key and value:
                    self.subsdict[key] = value

    @classmethod
    def subs(cls, str, i):
        if "%" in str:
            return str % i
        else:
            return str
    
    def doScript(self, script):
        # Create argument list that varies for each threaded client. Basically use a separate
        # server account for each client.
        def runner(*args):
            """
            Test runner method. 
            @param *args:
            """
            
            if self.logging:
                print "Start: %s" % (args[0]["moresubs"]["$userid1:"],)
            try:
                mgr = manager(level=manager.LOG_NONE)
                result, timing = mgr.runWithOptions(*args[1:], **args[0])
                if self.logging:
                    print "Done: %s" % (args[0]["moresubs"]["$userid1:"],)
            except Exception, e:
                print "Thread run exception: %s" % (str(e),)
    
        args = []
        for i in range(1, self.clients + 1):
            moresubs = {}
            for key, value in self.subsdict.iteritems():
                moresubs[key] = self.subs(value, i)
            args.append(({"moresubs": moresubs}, self.subs(self.serverinfo, i), "", [self.subs(script, i)]))
        for arg in args:
            runner(*arg)
    
    def doStart(self, silent):
        if self.startscript:
            if not silent:
                print "Runnning start script %s" % (self.startscript,)
            self.doScript(self.startscript)
    
    def doEnd(self, silent):
        if self.endscript:
            if not silent:
                print "Runnning end script %s" % (self.endscript,)
            self.doScript(self.endscript)

    def doLoadRamping(self, offset = 0):
        # Cummulative results
        allresults = []
        
        for test in self.tests:
            failed = [False]
            result = [0.0, 0.0, 0.0]
            results = []
        
            endtime = time.time() + START_DELAY + test[2]

            def runner(*args):
                """
                Test runner method. 
                @param *args:
                """
                
                while(True):
                    if self.logging:
                        print "Start: %s" % (args[0]["moresubs"]["$userid1:"],)
                    try:
                        mgr = manager(level=manager.LOG_NONE)
                        result, timing = mgr.runWithOptions(*args[1:], **args[0])
                        if result > 0:
                            failed[0] = True
                        results.append((time.time(), timing))
                        if divmod(len(results), 10)[1] == 0:
                            print len(results)
                        if self.logging:
                            print "Done: %s %.3f" % (args[0]["moresubs"]["$userid1:"], timing,)
                    except Exception, e:
                        print "Thread run exception: %s" % (str(e),)
                    if time.time() > endtime:
                        break
                    #time.sleep(randrange(0, 100)/100.0 * test[1])
        
            # Create argument list that varies for each threaded client. Basically use a separate
            # server account for each client.
            args = []
            for i in range(1 + offset, test[0] + 1 + offset):
                moresubs = {}
                for key, value in self.subsdict.iteritems():
                    moresubs[key] = self.subs(value, i)
                args.append(({"moresubs": moresubs}, self.subs(self.serverinfo, i), "", [self.subs(self.testinfo, i)]))
        
            if self.threads:
                # Run threads by queuing up a set of timers set to start 5 seconds + random time
                # after thread is actually started. The random time is spread over the interval
                # we are testing over. Wait for all threads to finish.
                timers = []
                for arg in args:
                    sleeper = START_DELAY + randrange(0, 100)/100.0 * test[1]
                    timers.append(Timer(sleeper, runner, arg))
            
                for thread in timers:
                    thread.start( )
            
                for thread in timers:
                    thread.join(None)
            else:
                # Just execute each client request one after the other.
                for arg in args:
                    runner(*arg)
    
            # Average over 1 sec intervals
            bins = {}
            for timestamp, timing in results:
                bins.setdefault(int(timestamp), []).append(timing)
            avbins = {}
            for key, values in bins.iteritems():
                average = 0.0
                for i in values:
                    average += i
                average /= len(values)
                avbins[key] = (average, len(values),)
            
            avkeys = avbins.keys()
            avkeys.sort()
            rawresults = []
            average_time = 0.0
            average_clients = 0.0
            for i in avkeys:
                rawresults.append((i, avbins[i][0], avbins[i][1]))
                average_time += avbins[i][0]
                average_clients += avbins[i][1]
            average_time /= len(avkeys)
            average_clients /= len(avkeys)
        
            allresults.append((rawresults, test[0], average_clients, average_time,))
    
        return allresults
