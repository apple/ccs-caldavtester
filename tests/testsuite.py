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
Class that encapsulates a series of tests.
"""

from tests.test import test
import tests.xmlDefs

class testsuite( object ):
    """
    Maintains a list of tests to run as part of a 'suite'.
    """
    __slots__  = ['name', 'ignore', 'tests']
    
    def __init__( self ):
        self.name = ""
        self.ignore = False
        self.tests = []
    
    def parseXML( self, node ):
        self.name = node.getAttribute( tests.xmlDefs.ATTR_NAME )
        self.ignore = node.getAttribute( tests.xmlDefs.ATTR_IGNORE ) == tests.xmlDefs.ATTR_VALUE_YES

        test_nodes = node.getElementsByTagName( tests.xmlDefs.ELEMENT_TEST )
        for child in test_nodes:
            t = test()
            t.parseXML( child )
            self.tests.append( t )

    def dump( self ):
        print "\nTest Suite:"
        print "    name: %s" % self.name
        for iter in self.tests:
            iter.dump()
