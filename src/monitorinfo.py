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
Class that encapsulates the server information for CalDAV monitoring.
"""

import src.xmlDefs

class monitorinfo( object ):
    """
    Maintains information about the monitoring test scenario.
    """
    __slots__  = ['logging', 'period', 'serverinfo', 'startscript', 'testinfo', 'endscript', 'warningtime', 'subsdict']

    def __init__( self ):
        self.logging = False
        self.period = 1.0
        self.serverinfo = ""
        self.startscript = ""
        self.testinfo = ""
        self.endscript = ""
        self.warningtime = 1.0
        self.subsdict = {}

    def parseXML( self, node ):
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_LOGGING:
                self.logging = child.getAttribute( src.xmlDefs.ATTR_ENABLE ) != src.xmlDefs.ATTR_VALUE_NO
            elif child._get_localName() == src.xmlDefs.ELEMENT_PERIOD:
                self.period = float(child.firstChild.data)
            elif child._get_localName() == src.xmlDefs.ELEMENT_SERVERINFO:
                self.serverinfo = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_START:
                if child.firstChild is not None:
                    self.startscript = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_TESTINFO:
                self.testinfo = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_END:
                if child.firstChild is not None:
                    self.endscript = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_WARNINGTIME:
                self.warningtime = float(child.firstChild.data)
            elif child._get_localName() == src.xmlDefs.ELEMENT_SUBSTITUTIONS:
                self.parseSubstitutionsXML(child)

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
