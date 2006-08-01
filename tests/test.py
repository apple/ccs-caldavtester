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
Class that encapsulates a single CalDAV test.
"""

from tests.request import request
import tests.xmlDefs

class test( object ):
    """
    A single test which can be comprised of multiple requests. The test can
    be run more than once, and timing information gathered and averaged across
    all runs.
    """
    __slots__  = ['name', 'details', 'count', 'stats', 'ignore', 'description', 'requests']
    
    def __init__( self ):
        self.name = ""
        self.details = False
        self.count = 1
        self.stats = False
        self.ignore = False
        self.description = ""
        self.requests = []
    
    def parseXML( self, node ):
        self.name = node.getAttribute( tests.xmlDefs.ATTR_NAME )
        self.details = node.getAttribute( tests.xmlDefs.ATTR_DETAILS ) == tests.xmlDefs.ATTR_VALUE_YES
        self.count = node.getAttribute( tests.xmlDefs.ATTR_COUNT )
        if self.count == '':
            self.count = 1
        else:
            self.count = int(self.count)
        self.stats = node.getAttribute( tests.xmlDefs.ATTR_STATS ) == tests.xmlDefs.ATTR_VALUE_YES
        self.ignore = node.getAttribute( tests.xmlDefs.ATTR_IGNORE ) == tests.xmlDefs.ATTR_VALUE_YES

        for child in node._get_childNodes():
            if child._get_localName() == tests.xmlDefs.ELEMENT_DESCRIPTION:
                self.description = child.firstChild.data

        # get request
        self.requests = request.parseList( node )

    def dump( self ):
        print "\nTEST: %s" % self.name
        print "    description: %s" % self.description
        for req in self.requests:
            req.dump()
