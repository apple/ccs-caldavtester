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
Class that encapsulates the server information for a CalDAV test run.
"""

import tests.xmlDefs

class serverinfo( object ):
    """
    Maintains information about the server beiung targetted.
    """
    __slots__  = ['host', 'port', 'ssl', 'calendarpath', 'user', 'pswd', 'hostsubs', 'pathsubs', 'serverfilepath']

    hostsubs = ""
    pathsubs = ""

    @classmethod
    def subs(cls, str):
        return str.replace("$host:", serverinfo.hostsubs).replace("$pathprefix:", serverinfo.pathsubs)

    def __init__( self ):
        self.host = ""
        self.port = 80
        self.ssl = False
        self.calendarpath = ""
        self.user = ""
        self.pswd = ""
        self.serverfilepath = ""
    
    def parseXML( self, node ):
        for child in node._get_childNodes():
            if child._get_localName() == tests.xmlDefs.ELEMENT_HOST:
                self.host = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_PORT:
                self.port = int( child.firstChild.data )
            elif child._get_localName() == tests.xmlDefs.ELEMENT_SSL:
                self.ssl = True
            elif child._get_localName() == tests.xmlDefs.ELEMENT_CALENDARPATH:
                self.calendarpath = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_USER:
                self.user = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_PSWD:
                self.pswd = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_HOSTSUBS:
                if child.firstChild is not None:
                    serverinfo.hostsubs = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_PATHSUBS:
                if child.firstChild is not None:
                    serverinfo.pathsubs = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_SERVERFILEPATH:
                if child.firstChild is not None:
                    self.serverfilepath = child.firstChild.data
