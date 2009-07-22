##
# Copyright (c) 2006-2009 Apple Inc. All rights reserved.
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

"""
Class that encapsulates a series of tests.
"""

from src.test import test
import src.xmlDefs

class testsuite( object ):
    """
    Maintains a list of tests to run as part of a 'suite'.
    """
    
    def __init__( self, manager ):
        self.manager = manager
        self.name = ""
        self.ignore = False
        self.require_features = set()
        self.tests = []
    
    def missingFeatures(self):
        return self.require_features - self.manager.server_info.features

    def parseXML( self, node ):
        self.name = node.getAttribute( src.xmlDefs.ATTR_NAME )
        self.ignore = node.getAttribute( src.xmlDefs.ATTR_IGNORE ) == src.xmlDefs.ATTR_VALUE_YES

        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_REQUIRE_FEATURE:
                self.parseFeatures( child )
            elif child._get_localName() == src.xmlDefs.ELEMENT_TEST:
                t = test(self.manager)
                t.parseXML( child )
                self.tests.append( t )

    def parseFeatures(self, node):
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_FEATURE:
                self.require_features.add(child.firstChild.data.encode("utf-8"))

    def dump( self ):
        print "\nTest Suite:"
        print "    name: %s" % self.name
        for iter in self.tests:
            iter.dump()
