##
# Copyright (c) 2006-2007 Apple Inc. All rights reserved.
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

class serverinfo( object ):
    """
    Maintains information about the server beiung targetted.
    """
    __slots__  = ['host', 'port', 'ssl', 'calendarpath', 'user', 'pswd', 'serverfilepath', 'subsdict', 'extrasubsdict',]


    def __init__( self ):
        self.host = ""
        self.port = 80
        self.ssl = False
        self.calendarpath = ""
        self.user = ""
        self.pswd = ""
        self.serverfilepath = ""
        self.subsdict = {}
        self.extrasubsdict = {}

    def subs(self, str, db=None):
        if db is None:
            db = self.subsdict
        for key, value in db.iteritems():
            str = str.replace(key, value)
        return str

    def addsubs(self, items, db=None):
        if db is None:
            db = self.subsdict
        for key, value in items.iteritems():
            db[key] = value
   
        if db is None:
            self.updateParams()
    
    def hasextrasubs(self):
        return len(self.extrasubsdict) > 0

    def extrasubs(self, str):
        return self.subs(str, self.extrasubsdict)

    def addextrasubs(self, items):
        self.addsubs(items, self.extrasubsdict)
        
    def parseXML( self, node ):
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_HOST:
                self.host = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_PORT:
                self.port = int( child.firstChild.data )
            elif child._get_localName() == src.xmlDefs.ELEMENT_SSL:
                self.ssl = True
            elif child._get_localName() == src.xmlDefs.ELEMENT_SERVERFILEPATH:
                if child.firstChild is not None:
                    self.serverfilepath = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_SUBSTITUTIONS:
                self.parseSubstitutionsXML(child)
   
        self.updateParams()

    def updateParams(self):         
        # Now cache some useful substitutions
        if "$calendarpath1:" not in self.subsdict:
            raise ValueError, "Must have $calendarpath1: substitution"
        self.calendarpath = self.subsdict["$calendarpath1:"]
        if "$userid1:" not in self.subsdict:
            raise ValueError, "Must have $userid1: substitution"
        self.user = self.subsdict["$userid1:"]
        if "$pswd1:" not in self.subsdict:
            raise ValueError, "Must have $pswd1: substitution"
        self.pswd = self.subsdict["$pswd1:"]

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
