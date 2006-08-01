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
Class that encapsulates the information for populating a CalDAV server.
"""

from utils import webdav
from tests.account import account

import tests.xmlDefs

class populate( object ):
    """
    Maintains information about accounts to be created on the server.
    """
    __slots__  = ['manager', 'description', 'path', 'accounts']

    def __init__( self, manager ):
        self.manager = manager
        self.description = ""
        self.path = None
        self.accounts = []
    
    def parseXML( self, node ):
        for child in node._get_childNodes():
            if child._get_localName() == tests.xmlDefs.ELEMENT_DESCRIPTION:
                self.description = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_PATH:
                self.path = child.firstChild.data
            elif child._get_localName() == tests.xmlDefs.ELEMENT_ACCOUNT:
                acct = account()
                acct.parseXML(child)
                self.accounts.extend(acct.expand())

    def generateAccounts(self):
        """
        Generate each account on the server.
        """
        
        # Verify path and create it on the server
        if not self.path:
            raise ValueError("Path for account population not set up.")
        
        if not webdav.ResourceExists(self.manager.server_info, self.path).run():
            if not webdav.MakeCollection(self.manager.server_info, self.path).run():
                raise ValueError("Could not make collection for population set up")

        for account in self.accounts:
            self.manager.log("Generating account: %s" % (account.name,))
            account.generate(self.manager.server_info, self.path)
            
    def removeAccounts(self):
        """
        Remove each account on the server.
        """
        for account in self.accounts:
            self.manager.log("Removing account: %s" % (account.name,))
            account.remove(self.manager.server_info, self.path)

        # Finally remove path
        webdav.Delete(self.manager.server_info, self.path).run()
