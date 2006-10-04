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

import tests.xmlDefs

class serverinfo( object ):
    """
    Maintains information about the server beiung targetted.
    """
    __slots__  = ['host', 'port', 'ssl', 'calendarpath', 'user', 'pswd', 'hostsubs', 'pathsubs', 'serverfilepath']

    hostsubs = ""
    pathsubs = ""
    subsdict = {}

    @classmethod
    def subs(cls, str):
        for key, value in serverinfo.subsdict.iteritems():
            str = str.replace(key, value)
        return str

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
                    serverinfo.subsdict["$host"] = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_PATHSUBS:
                if child.firstChild is not None:
                    serverinfo.subsdict["$pathprefix"] = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_SERVERFILEPATH:
                if child.firstChild is not None:
                    self.serverfilepath = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_SUBSTITUTIONS:
                self.parseSubstitutionsXML(child)

    def parseSubstitutionsXML(self, node):
        for child in node._get_childNodes():
            if child._get_localName() == tests.xmlDefs.ELEMENT_SUBSTITUTION:
                key = None
                value = None
                for schild in child._get_childNodes():
                    if schild._get_localName() == tests.xmlDefs.ELEMENT_KEY:
                        key = schild.firstChild.data
                    elif schild._get_localName() == tests.xmlDefs.ELEMENT_VALUE:
                        value = schild.firstChild.data
                if key and value:
                    self.subsdict[key] = value
