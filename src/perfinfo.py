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
Class that encapsulates the server information for a CalDAV test run.
"""

import src.xmlDefs

class perfinfo( object ):
    """
    Maintains information about the performance test scenario.
    """
    __slots__  = ['clients', 'threads', 'logging', 'tests', 'serverinfo', 'testinfo', 'subsdict']

    def __init__( self ):
        self.clients = 20
        self.threads = True
        self.logging = False
        self.tests = []
        self.serverinfo = ""
        self.testinfo = ""
        self.subsdict = {}

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
            elif child._get_localName() == src.xmlDefs.ELEMENT_TESTINFO:
                self.testinfo = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_SUBSTITUTIONS:
                self.parseSubstitutionsXML(child)

    def parseTestsXML(self, node):
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_TEST:
                spread = None
                runs = None
                for schild in child._get_childNodes():
                    if schild._get_localName() == src.xmlDefs.ELEMENT_SPREAD:
                        spread = float(schild.firstChild.data)
                    elif schild._get_localName() == src.xmlDefs.ELEMENT_RUNS:
                        runs = int(schild.firstChild.data)
                if spread and runs:
                    self.tests.append((spread, runs,))

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
