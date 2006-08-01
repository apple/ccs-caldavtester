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
