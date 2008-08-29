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

from vobject.base import readOne, ContentLine
from vobject.base import Component
from difflib import unified_diff
import StringIO

"""
Verifier that checks the response body for an exact match to data in a file.
"""

class Verifier(object):
    
    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable
        # Get arguments
        files = args.get("filepath", [])
        
        # status code must be 200, 207
        if response.status not in (200,207):
            return False, "        HTTP Status Code Wrong: %d" % (response.status,)
        
        # look for response data
        if not respdata:
            return False, "        No response body"
        
        # look for one file
        if len(files) != 1:
            return False, "        No file to compare response to"
        
        # read in all data from specified file
        fd = open( files[0], "r" )
        try:
            try:
                data = fd.read()
            finally:
                fd.close()
        except:
            data = None

        if data is None:
            return False, "        Could not read data file"

        data = manager.server_info.subs(data)
        
        def removePropertiesParameters(component):
            
            for item in tuple(component.getChildren()):
                if isinstance(item, Component):
                    removePropertiesParameters(item)
                elif isinstance(item, ContentLine):
                    
                    # Always remove DTSTAMP
                    if item.name == "DTSTAMP":
                        component.remove(item)
                    elif item.name == "X-CALENDARSERVER-ATTENDEE-COMMENT":
                        if item.params.has_key("X-CALENDARSERVER-DTSTAMP"):
                            item.params["X-CALENDARSERVER-DTSTAMP"] = ["20080101T000000Z"]

        s = StringIO.StringIO(respdata)
        resp_calendar = readOne(s)
        removePropertiesParameters(resp_calendar)
        respdata = resp_calendar.serialize()
        
        s = StringIO.StringIO(data)
        data_calendar = readOne(s)
        removePropertiesParameters(data_calendar)
        data = data_calendar.serialize()
        
        result = respdata == data
                
        if result:
            return True, ""
        else:
            error_diff = "\n".join([line for line in unified_diff(data.split("\n"), respdata.split("\n"))])
            return False, "        Response data does not exactly match file data%s" % (error_diff,)
