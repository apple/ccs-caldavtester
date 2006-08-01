##
# Copyright (c) 2006 Apple Computer, Inc. All rights reserved.
#
# This file contains Original Code and/or Modifications of Original Code
# as defined in and that are subject to the Apple Public Source License
# Version 2.0 (the 'License'). You may not use this file except in
# compliance with the License. Please obtain a copy of the License at
# http://www.opensource.apple.com/apsl/ and read it before using this
# file.
#
# The Original Code and all software distributed under the License are
# distributed on an 'AS IS' basis, WITHOUT WARRANTY OF ANY KIND, EITHER
# EXPRESS OR IMPLIED, AND APPLE HEREBY DISCLAIMS ALL SUCH WARRANTIES,
# INCLUDING WITHOUT LIMITATION, ANY WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE, QUIET ENJOYMENT OR NON-INFRINGEMENT.
# Please see the License for the specific language governing rights and
# limitations under the License.
#
# DRI: Cyrus Daboo, cdaboo@apple.com
##

"""
Class to manage the testing process.
"""

import time
import httplib
from tests.populate import populate
import os

from tests.caldavtest import caldavtest
from tests.serverinfo import serverinfo
import getopt
import sys
import tests.xmlDefs
import xml.dom.minidom

# Exceptions

EX_INVALID_CONFIG_FILE = "Invalid Config File"
EX_FAILED_REQUEST = "HTTP Request Failed"

class manager(object):

    """
    Main class that runs test suites defined in an XML config file.
    """
    __slots__  = ['server_info', 'populator', 'depopulate', 'tests', 'textMode']

    def __init__( self, text=True ):
        self.server_info = serverinfo()
        self.populator = None
        self.depopulate = False
        self.tests = []
        self.textMode = text
    
    def log(self, str, indent = 0, indentStr = " ", after = 1, before = 0):
        if self.textMode:
            if before:
                print "\n" * before,
            if indent:
                print indentStr * indent,
            print str,
            if after:
                print "\n" * after,

    def readXML( self, serverfile, populatorfile, testfiles, all ):

        self.log("Reading Server Info from \"%s\"" % serverfile, after=2)
    
        # Open and parse the server config file
        fd = open(serverfile, "r")
        doc = xml.dom.minidom.parse( fd )
        fd.close()

        # Verify that top-level element is correct
        serverinfo_node = doc._get_documentElement()
        if serverinfo_node._get_localName() != tests.xmlDefs.ELEMENT_SERVERINFO:
            raise EX_INVALID_CONFIG_FILE
        if not serverinfo_node.hasChildNodes():
            raise EX_INVALID_CONFIG_FILE
        self.server_info.parseXML(serverinfo_node)
        
        # Open and parse the populator config file
        if populatorfile:
            self.log("Reading Populator Info from \"%s\"" % populatorfile, after=2)
    
            fd = open(populatorfile, "r")
            doc = xml.dom.minidom.parse( fd )
            fd.close()

            # Verify that top-level element is correct
            populate_node = doc._get_documentElement()
            if populate_node._get_localName() != tests.xmlDefs.ELEMENT_POPULATE:
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
            caldavtest_node = doc._get_documentElement()
            if caldavtest_node._get_localName() != tests.xmlDefs.ELEMENT_CALDAVTEST:
                self.log("Ignoring file \"%s\" because it is not a test file" % (testfile,), after=2)
                continue
            if not caldavtest_node.hasChildNodes():
                raise EX_INVALID_CONFIG_FILE
            self.log("Reading Test Details from \"%s\"" % testfile, after=2)
                
            # parse all the config data
            test = caldavtest(self, testfile)
            test.parseXML(caldavtest_node)
            
            # ignore if all mode and ignore-all is set
            if not all or not test.ignore_all:
                self.tests.append(test)

    def readCommandLine(self):
        sname = "serverinfo.xml"
        pname = None
        fnames = []
        all = False
        options, args = getopt.getopt(sys.argv[1:], "s:p:d", ["all"])
        
        # Process single options
        for option, value in options:
            if option == "-s":
                sname = value
            elif option == "-p":
                pname = value
            elif option == "-d":
                self.depopulate = True
            elif option == "--all":
                all = True
                files = os.listdir(os.getcwd())
                for file in files:
                    if file.endswith(".xml"):
                        fnames.append(file)

        # Remove any server info file from files enuerated by --all
        fnames[:] = [x for x in fnames if (x != sname) and (not pname or (x != pname))]

        # Process any files argumentsd as test configs
        for f in args:
            fnames.append(f)
        
        self.readXML(sname, pname, fnames, all)

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

        self.log("Overall Results: %d PASSED, %d FAILED, %d IGNORED" % (ok, failed, ignored), before=2, indent=4)
        self.log("Total time: %d secs" % (endTime- startTime,))

        sys.exit(failed)

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
        
