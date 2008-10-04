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
##

"""
Class that encapsulates the account information for populating a CalDAV server.
"""

from utilities import webdav
import copy
import md5
import os
import src.xmlDefs

class account( object ):
    """
    Maintains information about an account on the server.
    """
    __slots__  = ['name', 'count', 'countarg', 'calendars', 'datasource', 'dataall', 'datasubstitute']

    def __init__( self ):
        self.name = ""
        self.count = 1
        self.countarg = None
        self.calendars = []
        self.datasource = None
        self.dataall = True
        self.datasubstitute = True
    
    def expand(self):
        """
        Create a list of new accounts from this one by expanding the
        name list using the supplied count and  countargs.
        """
        accounts = []
        if (self.count > 1) and (self.name.find(self.countarg)):
            if self.count >= 10:
                strfmt = "%0" + str(len(str(self.count))) + "d"
            else:
                strfmt = "%d"
            name = self.name.replace(self.countarg, strfmt)
            for i in range(1, self.count + 1):
                expname = (name % i)
                newacct = copy.copy(self)
                newacct.name = expname
                accounts.append(newacct)
        else:
            accounts.append(self)
        return accounts

    def generate(self, server_info, path):
        """
        Create the necessary resources on the server for this account.
        """
        
        # Create user collection
        path += self.name + "/"
        if not webdav.ResourceExists(server_info, path).run():
            if not webdav.MakeCollection(server_info, path).run():
                raise ValueError("Could not make collection for user %s" % (self.name,))

        # Create calendars within user collection
        for calendar in self.calendars:
            calendar.generate(server_info, path)
            
    def remove(self, server_info, path):
        """
        Remove the generated resources on the server for this account.
        """
        path += self.name + "/"
        webdav.Delete(server_info, path).run()

    def parseXML( self, node ):
        self.count = node.getAttribute( src.xmlDefs.ATTR_COUNT )
        if self.count == '':
            self.count = src.xmlDefs.ATTR_DEFAULT_COUNT
        else:
            self.count = int(self.count)
        self.countarg = node.getAttribute( src.xmlDefs.ATTR_COUNTARG )
        if self.countarg == '':
            self.countarg = src.xmlDefs.ATTR_DEFAULT_COUNTARG

        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_NAME:
                self.name = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_CALENDARS:
                cal = calendar(self)
                cal.parseXML(child)
                self.calendars.extend(cal.expand())


class calendar(object):
    __slots__ = ['account', 'name', 'count', 'countarg', 'datasource', 'datacount', 'datacountarg', 'dataall', 'datasubstitute']
    
    def __init__(self, account):
        self.account = account
        self.name = None
        self.count = 1
        self.countarg = None
        self.datasource = None
        self.datacount = 1
        self.datacountarg = None
        self.dataall = True
        self.datasubstitute = True
        
    def expand(self):
        """
        Create a list of new calendars from this one by expanding the
        name list using the supplied count and  countargs.
        """
        calendars = []
        if (self.count > 1) and (self.name.find(self.countarg)):
            if self.count >= 10:
                strfmt = "%0" + str(len(str(self.count))) + "d"
            else:
                strfmt = "%d"
            name = self.name.replace(self.countarg, strfmt)
            for i in range(1, self.count + 1):
                expname = (name % i)
                newcal = copy.copy(self)
                newcal.name = expname
                calendars.append(newcal)
        else:
            calendars.append(self)
        return calendars

    def generate(self, server_info, path):
        """
        Create the necessary resources on the server for this calendar.
        """
        
        # Create calendars within user collection
        cpath = path + self.name + "/"
        if not webdav.ResourceExists(server_info, cpath).run():
            if not webdav.MakeCalendar(server_info, cpath).run():
                raise ValueError("Could not make calendar collection %s for user %s" % (self.name, account.name))
    
        # Now generate data in the calendar
        if not self.datasource:
            return
        dir = os.getcwd() + "/" + self.datasource
        dataitems = os.listdir(dir)
        for item in dataitems:
            if item.endswith(".ics"):
                fname = dir + item
                self.generateItems(server_info, cpath, fname)

    def generateItems(self, server_info, cpath, item):
        """
        Generate one or more iCalendar resources from the supplied data file,
        doing appropriate substitutions in the data.
        """
        file_object = open(item)
        try:
            caldata = file_object.read( )
        finally:
            file_object.close( )

        if self.datacount == 1:
            rpath = cpath + md5.new(cpath + item + str(self.count)).hexdigest() + ".ics"
            webdav.Put(server_info, rpath, "text/calendar; charset=utf-8", caldata).run()
        else:
            for ctr in range(1, self.datacount + 1):
                data = caldata.replace(self.datacountarg, str(ctr))
                rpath = cpath + md5.new(cpath + item + str(self.count) + str(ctr)).hexdigest() + ".ics"
                webdav.Put(server_info, rpath, "text/calendar; charset=utf-8", data).run()

    def parseXML( self, node ):
        self.count = node.getAttribute( src.xmlDefs.ATTR_COUNT )
        if self.count == '':
            self.count = src.xmlDefs.ATTR_DEFAULT_COUNT
        else:
            self.count = int(self.count)
        self.countarg = node.getAttribute( src.xmlDefs.ATTR_COUNTARG )
        if self.countarg == '':
            self.countarg = src.xmlDefs.ATTR_DEFAULT_COUNTARG
        self.dataall = src.xmlDefs.ATTR_MODE == src.xmlDefs.ATTR_VALUE_ALL
        self.datasubstitute = src.xmlDefs.ATTR_SUBSTITUTIONS == src.xmlDefs.ATTR_VALUE_YES

        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_NAME:
                self.name = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_DATASOURCE:
                self.datacount = child.getAttribute( src.xmlDefs.ATTR_COUNT )
                if self.datacount == '':
                    self.datacount = src.xmlDefs.ATTR_DEFAULT_COUNT
                else:
                    self.datacount = int(self.datacount)
                self.datacountarg = child.getAttribute( src.xmlDefs.ATTR_COUNTARG )
                if self.datacountarg == '':
                    self.datacountarg = src.xmlDefs.ATTR_DEFAULT_COUNTARG
                self.datasource = child.firstChild.data
    
