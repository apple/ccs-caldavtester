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
