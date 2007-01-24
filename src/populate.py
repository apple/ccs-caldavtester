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
Class that encapsulates the information for populating a CalDAV server.
"""

from src.account import account
from utils import webdav
import src.xmlDefs

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
            if child._get_localName() == src.xmlDefs.ELEMENT_DESCRIPTION:
                self.description = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_PATH:
                self.path = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_ACCOUNT:
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
