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
Class that encapsulates the server information for CalDAV monitoring.
"""

from src.xmlUtils import getDefaultAttributeValue
from src.xmlUtils import getYesNoAttributeValue
from src.xmlUtils import readOneStringElement
from src.xmlUtils import readStringElementList
import src.xmlDefs

class monitorinfo( object ):
    """
    Maintains information about the monitoring test scenario.
    """
    __slots__  = [
        'name',
        'logging',
        'period',
        'timeout',
        'serverinfo',
        'startscript',
        'testinfo',
        'endscript',
        'warningtime',
        'notify',
        'notify_from',
        'notify_time_exceeded',
        'notify_request_failed',
        'notify_interval',
        'notify_subject',
        'notify_body',
    ]

    def __init__( self ):
        self.name = ""
        self.logging = False
        self.period = 1.0
        self.timeout = 60
        self.serverinfo = ""
        self.startscript = ""
        self.testinfo = ""
        self.endscript = ""
        self.warningtime = 1.0
        self.notify = None
        self.notify_from = None
        self.notify_time_exceeded = False
        self.notify_request_failed = False
        self.notify_interval = 15
        self.notify_subject = None
        self.notify_body = None

    def parseXML( self, node ):
        
        self.name = getDefaultAttributeValue(node, src.xmlDefs.ATTR_NAME, "")
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_LOGGING:
                self.logging = getYesNoAttributeValue(child, src.xmlDefs.ATTR_ENABLE)
            elif child._get_localName() == src.xmlDefs.ELEMENT_PERIOD:
                self.period = float(child.firstChild.data)
            elif child._get_localName() == src.xmlDefs.ELEMENT_TIMEOUT:
                self.timeout = int(child.firstChild.data)
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
            elif child._get_localName() == src.xmlDefs.ELEMENT_NOTIFY:
                self.notify_time_exceeded = getYesNoAttributeValue(child, src.xmlDefs.ATTR_TIME_EXCEEDED)
                self.notify_request_failed = getYesNoAttributeValue(child, src.xmlDefs.ATTR_REQUEST_FAILED)
                self.notify_interval = int(getDefaultAttributeValue(child, src.xmlDefs.ATTR_INTERVAL, "15"))
                self.notify = readStringElementList(child, src.xmlDefs.ELEMENT_MAILTO)
                self.notify_from = readOneStringElement(child, src.xmlDefs.ELEMENT_MAILFROM)
                self.notify_subject = readOneStringElement(child, src.xmlDefs.ELEMENT_SUBJECT)
                self.notify_body = readOneStringElement(child, src.xmlDefs.ELEMENT_BODY)
