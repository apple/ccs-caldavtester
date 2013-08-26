##
# Copyright (c) 2013 Apple Inc. All rights reserved.
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

from difflib import unified_diff
import json

"""
Verifier that checks the response body for a semantic match to data in a file.
"""

class Verifier(object):

    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable
        # Get arguments
        files = args.get("filepath", [])
        caldata = args.get("data", [])
        filters = args.get("filter", [])

        if "EMAIL parameter" not in manager.server_info.features:
            filters.append("ATTENDEE:EMAIL")
            filters.append("ORGANIZER:EMAIL")
        filters.append("ATTENDEE:X-CALENDARSERVER-DTSTAMP")
        filters.append("CALSCALE")
        filters.append("PRODID")
        filters.append("DTSTAMP")
        filters.append("CREATED")
        filters.append("LAST-MODIFIED")
        filters.append("X-WR-CALNAME")

        for afilter in tuple(filters):
            if afilter[0] == "!" and afilter[1:] in filters:
                filters.remove(afilter[1:])
        filters = filter(lambda x: x[0] != "!", filters)

        # status code must be 200, 201, 207
        if response.status not in (200, 201, 207):
            return False, "        HTTP Status Code Wrong: %d" % (response.status,)

        # look for response data
        if not respdata:
            return False, "        No response body"

        # look for content-type
        hdrs = response.msg.getheaders("Content-Type")
        if hdrs is None or len(hdrs) == 0:
            return False, "        No Content-Type header"
        if len(hdrs) != 1:
            return False, "        Wrong number of Content-Type headers"
        if hdrs[0].split(";")[0] != "application/calendar+json":
            return False, "        Wrong Content-Type header"

        # look for one file
        if len(files) != 1 and len(caldata) != 1:
            return False, "        No file to compare response to"

        # read in all data from specified file or use provided data
        if len(files):
            fd = open(files[0], "r")
            try:
                try:
                    data = fd.read()
                finally:
                    fd.close()
            except:
                data = None
        else:
            data = caldata[0] if len(caldata) else None

        if data is None:
            return False, "        Could not read data file"

        data = manager.server_info.extrasubs(manager.server_info.subs(data))

        def removePropertiesParameters(component):

            # component = [name, props-array, subcomponent-array]

            for subcomponent in component[2]:
                removePropertiesParameters(subcomponent)

            for pos, property in reversed(tuple(enumerate(component[1]))):

                # property = [name, param-dict, value-type, values...]

                # Always reset DTSTAMP on these properties
                if property[0] in ("ATTENDEE".lower(), "X-CALENDARSERVER-ATTENDEE-COMMENT".lower()):
                    if "X-CALENDARSERVER-DTSTAMP".lower() in property[1]:
                        property[1]["X-CALENDARSERVER-DTSTAMP".lower()] = "20080101T000000Z"

                for filter in filters:
                    if ":" in filter:
                        propname, parameter = filter.split(":")
                        if property[0] == propname.lower():
                            if parameter.lower in property[1]:
                                del property[1][parameter.lower()]
                    else:
                        if property[0] == filter.lower():
                            del component[1][pos]

        try:
            resp_calendar = json.loads(respdata)
            removePropertiesParameters(resp_calendar)
            respdata = json.dumps(resp_calendar)

            data_calendar = json.loads(data)
            removePropertiesParameters(data_calendar)
            data = json.dumps(data_calendar)

            result = respdata == data

            if result:
                return True, ""
            else:
                error_diff = "\n".join([line for line in unified_diff(data.split("\n"), respdata.split("\n"))])
                return False, "        Response data does not exactly match file data%s" % (error_diff,)
        except Exception, e:
            return False, "        Response data is not calendar data: %s" % (e,)
