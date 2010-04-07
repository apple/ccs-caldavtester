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
Verifier that checks the response of a free-busy-query.
"""

from vobject.base import VObjectError
from vobject.base import readOne
from vobject.icalendar import periodToString
import StringIO
import datetime
from xml.etree.ElementTree import ElementTree
from xml.parsers.expat import ExpatError

class Verifier(object):
    
    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable
        
        # Must have status 200
        if response.status != 200:
            return False, "        HTTP Status Code Wrong: %d" % (response.status,)

        # Get expected FREEBUSY info
        users = args.get("attendee", [])
        busy = args.get("busy", [])
        tentative = args.get("tentative", [])
        unavailable = args.get("unavailable", [])
        
        # Extract each calendar-data object
        try:
            tree = ElementTree(file=StringIO.StringIO(respdata))
        except ExpatError:
            return False, "           Could not parse proper XML response\n"

        for calendar in tree.findall("/{urn:ietf:params:xml:ns:caldav}response/{urn:ietf:params:xml:ns:caldav}calendar-data"):
            # Parse data as calendar object
            try:
                s = StringIO.StringIO(calendar.text)
                calendar = readOne(s)
                
                # Check for calendar
                if calendar.name != "VCALENDAR":
                    raise ValueError("Top-level component is not a calendar: %s" % (calendar.name, ))
                
                # Only one component
                comps = list(calendar.components())
                if len(comps) != 1:
                    raise ValueError("Wrong number of components in calendar")
                
                # Must be VFREEBUSY
                fb = comps[0]
                if fb.name != "VFREEBUSY":
                    raise ValueError("Calendar contains unexpected component: %s" % (fb.name, ))
                
                # Check for attendee value
                for attendee in [x for x in fb.lines() if x.name == "ATTENDEE"]:
                    if attendee.value in users:
                        break
                else:
                    continue

                # Extract periods
                busyp = []
                tentativep = []
                unavailablep = []
                for fp in [x for x in fb.lines() if x.name == "FREEBUSY"]:
                    periods = fp.value
                    # Convert start/duration to start/end
                    for i in range(len(periods)):
                        if isinstance(periods[i][1], datetime.timedelta):
                            periods[i] = (periods[i][0], periods[i][0] + periods[i][1])
                    # Check param
                    fbtype = "BUSY"
                    if "FBTYPE" in fp.params:
                        fbtype = fp.params["FBTYPE"][0]
                    if fbtype == "BUSY":
                        busyp.extend(periods)
                    elif fbtype == "BUSY-TENTATIVE":
                        tentativep.extend(periods)
                    elif fbtype == "BUSY-UNAVAILABLE":
                        unavailablep.extend(periods)
                    else:
                        raise ValueError("Unknown FBTYPE: %s" % (fbtype,))
                
                # Set sizes must match
                if ((len(busy) != len(busyp)) or
                    (len(unavailable) != len(unavailablep)) or
                    (len(tentative) != len(tentativep))):
                    raise ValueError("Period list sizes do not match.")
                
                # Convert to string sets
                busy = set(busy)
                busyp[:] = [periodToString(x) for x in busyp]
                busyp = set(busyp)
                tentative = set(tentative)
                tentativep[:] = [periodToString(x) for x in tentativep]
                tentativep = set(tentativep)
                unavailable = set(unavailable)
                unavailablep[:] = [periodToString(x) for x in unavailablep]
                unavailablep = set(unavailablep)
    
                # Compare all periods
                if len(busyp.symmetric_difference(busy)):
                    raise ValueError("Busy periods do not match")
                elif len(tentativep.symmetric_difference(tentative)):
                    raise ValueError("Busy-tentative periods do not match")
                elif len(unavailablep.symmetric_difference(unavailable)):
                    raise ValueError("Busy-unavailable periods do not match")
                
                break
                    
            except VObjectError:
                return False, "        HTTP response data is not a calendar"
            except ValueError, txt:
                return False, "        HTTP response data is invalid: %s" % (txt,)
            
        return True, ""
