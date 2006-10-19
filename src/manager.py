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

"""
Class to manage the testing process.
"""

from src.populate import populate
from src.serverinfo import serverinfo
import getopt
import httplib
import os
import src.xmlDefs
import sys
import time
import xml.dom.minidom

# Exceptions

EX_INVALID_CONFIG_FILE = "Invalid Config File"
EX_FAILED_REQUEST = "HTTP Request Failed"

class manager(object):

    """
    Main class that runs test suites defined in an XML config file.
    """
    __slots__  = ['server_info', 'populator', 'depopulate', 'tests', 'textMode', 'logLevel']

    LOG_NONE    = 0
    LOG_LOW     = 1
    LOG_MEDIUM  = 2
    LOG_HIGH    = 3

    def __init__( self, text=True, level=LOG_HIGH ):
        self.server_info = serverinfo()
        self.populator = None
        self.depopulate = False
        self.tests = []
        self.textMode = text
        self.logLevel = level
    
    def log(self, level, str, indent = 0, indentStr = " ", after = 1, before = 0):
        if self.textMode and level <= self.logLevel:
            if before:
                print "\n" * before,
            if indent:
                print indentStr * indent,
            print str,
            if after:
                print "\n" * after,

    def readXML( self, serverfile, populatorfile, testfiles, all, moresubs = {} ):

        self.log(manager.LOG_HIGH, "Reading Server Info from \"%s\"" % serverfile, after=2)
    
        # Open and parse the server config file
        fd = open(serverfile, "r")
        doc = xml.dom.minidom.parse( fd )
        fd.close()

        # Verify that top-level element is correct
        serverinfo_node = doc._get_documentElement()
        if serverinfo_node._get_localName() != src.xmlDefs.ELEMENT_SERVERINFO:
            raise EX_INVALID_CONFIG_FILE
        if not serverinfo_node.hasChildNodes():
            raise EX_INVALID_CONFIG_FILE
        self.server_info.parseXML(serverinfo_node)
        self.server_info.addsubs(moresubs)
        
        # Open and parse the populator config file
        if populatorfile:
            self.log(manager.LOG_HIGH, "Reading Populator Info from \"%s\"" % populatorfile, after=2)
    
            fd = open(populatorfile, "r")
            doc = xml.dom.minidom.parse( fd )
            fd.close()

            # Verify that top-level element is correct
            populate_node = doc._get_documentElement()
            if populate_node._get_localName() != src.xmlDefs.ELEMENT_POPULATE:
                raise EX_INVALID_CONFIG_FILE
            if not populate_node.hasChildNodes():
                raise EX_INVALID_CONFIG_FILE
            self.populator = populate(self)
            self.populator.parseXML(populate_node)

        for testfile in testfiles:
            # Open and parse the config file
            fd = open( testfile, "r" )
            doc = xml.dom.minidom.parse( fd )
            fd.close()
            
            # Verify that top-level element is correct
            from src.caldavtest import caldavtest
            caldavtest_node = doc._get_documentElement()
            if caldavtest_node._get_localName() != src.xmlDefs.ELEMENT_CALDAVTEST:
                self.log(manager.LOG_HIGH, "Ignoring file \"%s\" because it is not a test file" % (testfile,), after=2)
                continue
            if not caldavtest_node.hasChildNodes():
                raise EX_INVALID_CONFIG_FILE
            self.log(manager.LOG_HIGH, "Reading Test Details from \"%s\"" % testfile, after=2)
                
            # parse all the config data
            test = caldavtest(self, testfile)
            test.parseXML(caldavtest_node)
            
            # ignore if all mode and ignore-all is set
            if not all or not test.ignore_all:
                self.tests.append(test)

    def readCommandLine(self):
        sname = "scripts/server/serverinfo.xml"
        pname = None
        dname = "scripts/tests"
        fnames = []
        all = False
        options, args = getopt.getopt(sys.argv[1:], "s:p:dx:", ["all"])
        
        # Process single options
        for option, value in options:
            if option == "-s":
                sname = value
            elif option == "-p":
                pname = value
            elif option == "-d":
                self.depopulate = True
            elif option == "-x":
                dname = value
            elif option == "--all":
                all = True
                
        if all:
            files = os.listdir(dname)
            for file in files:
                if file.endswith(".xml"):
                    fnames.append(dname + "/" + file)

        # Remove any server info file from files enuerated by --all
        fnames[:] = [x for x in fnames if (x != sname) and (not pname or (x != pname))]

        # Process any filesarguments as test configs
        for f in args:
            fnames.append(dname + "/" + f)
        
        self.readXML(sname, pname, fnames, all)

    def runWithOptions(self, sname, pname, fnames, moresubs, all = False, depopulate = False):
        self.depopulate = depopulate
        self.readXML(sname, pname, fnames, all, moresubs)
        return self.runAll()

    def runAll(self):
        
        if self.populator:
            self.runPopulate();

        startTime = time.time()
        ok = 0
        failed = 0
        ignored = 0
        try:
            for test in self.tests:
                o, f, i = test.run()
                ok += o
                failed += f
                ignored += i
        except:
            failed += 1
            import traceback
            traceback.print_exc()

        endTime = time.time()

        if self.populator and self.depopulate:
            self.runDepopulate()

        self.log(manager.LOG_LOW, "Overall Results: %d PASSED, %d FAILED, %d IGNORED" % (ok, failed, ignored), before=2, indent=4)
        self.log(manager.LOG_LOW, "Total time: %.3f secs" % (endTime- startTime,))

        return failed, endTime - startTime

    def runPopulate(self):
        self.populator.generateAccounts()
    
    def runDepopulate(self):
        self.populator.removeAccounts()

    def httpRequest(self, method, uri, headers, data):

        # Do the http request
        http = httplib.HTTPConnection( self.server_info.host, self.server_info.port )
        try:
            http.request( method, uri, data, headers )
        
            response = http.getresponse()
        
            respdata = response.read()

        finally:
            http.close()
        
        return response.status, respdata
        
