##
# Copyright (c) 2006-2016 Apple Inc. All rights reserved.
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
try:
    # pycalendar is optional
    from pycalendar.icalendar.calendar import Calendar
    from pycalendar.icalendar.componentrecur import ComponentRecur
    from pycalendar.parameter import Parameter
except ImportError:
    pass
import os

"""
Verifier that checks the response body for a semantic match to data in a file.
"""


class Verifier(object):

    def verify(self, manager, uri, response, respdata, args, is_json=False):  # @UnusedVariable
        # Get arguments
        files = args.get("filepath", [])
        if manager.data_dir:
            files = [os.path.join(manager.data_dir, f) for f in files]
        caldata = args.get("data", [])
        filters = args.get("filter", [])
        statusCode = args.get("status", ["200", "201", "207"])
        doTimezones = args.get("doTimezones", None)

        if "EMAIL parameter" not in manager.server_info.features:
            filters.append("ATTENDEE:EMAIL")
            filters.append("ORGANIZER:EMAIL")
        filters.extend(manager.server_info.calendardatafilters)

        for afilter in tuple(filters):
            if afilter[0] == "!" and afilter[1:] in filters:
                filters.remove(afilter[1:])
        filters = filter(lambda x: x[0] != "!", filters)

        if doTimezones is None:
            doTimezones = "timezones-by-reference" not in manager.server_info.features
        else:
            doTimezones = doTimezones == "true"

        # status code must be 200, 201, 207 or explicitly specified code
        if str(response.status) not in statusCode:
            return False, "        HTTP Status Code Wrong: %d" % (response.status,)

        # look for response data
        if not respdata:
            return False, "        No response body"

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

            if not doTimezones:
                for subcomponent in tuple(component.getComponents()):
                    if subcomponent.getType() == "VTIMEZONE":
                        component.removeComponent(subcomponent)

            for subcomponent in component.getComponents():
                removePropertiesParameters(subcomponent)

            if component.getType() == "VEVENT":
                if component.hasEnd():
                    component.editTimingStartDuration(component.getStart(), component.getEnd() - component.getStart())

            allProps = []
            for properties in component.getProperties().itervalues():
                allProps.extend(properties)
            for property in allProps:
                # Always reset DTSTAMP on these properties
                if property.getName() in ("ATTENDEE", "X-CALENDARSERVER-ATTENDEE-COMMENT"):
                    if property.hasParameter("X-CALENDARSERVER-DTSTAMP"):
                        property.replaceParameter(Parameter("X-CALENDARSERVER-DTSTAMP", "20080101T000000Z"))

                for filter in filters:
                    if ":" in filter:
                        propname, parameter = filter.split(":")
                        if property.getName() == propname:
                            if property.hasParameter(parameter):
                                property.removeParameters(parameter)
                    else:
                        if "=" in filter:
                            filter_name, filter_value = filter.split("=")
                            if property.getName() == filter_name and property.getValue().getValue() == filter_value:
                                component.removeProperty(property)
                        else:
                            if property.getName() == filter:
                                component.removeProperty(property)

        def reconcileRecurrenceOverrides(calendar1, calendar2):
            """
            Make sure that the same set of overridden components appears in both calendar objects.
            """
            def _getRids(calendar):
                """
                Get all the recurrence ids of the specified calendar.
                """
                results = set()
                master = None
                for subcomponent in calendar.getComponents():
                    if isinstance(subcomponent, ComponentRecur):
                        rid = subcomponent.getRecurrenceID()
                        if rid:
                            results.add(rid.duplicateAsUTC())
                        else:
                            master = subcomponent
                return results, master

            def _addOverrides(calendar, master, missing_rids):
                """
                Derive instances for the missing overrides in the specified calendar object.
                """
                if master is None or not missing_rids:
                    return
                for rid in missing_rids:
                    # If we were fed an already derived component, use that, otherwise make a new one
                    newcomp = calendar.deriveComponent(rid)
                    if newcomp is not None:
                        calendar.addComponent(newcomp)

            rids1, master1 = _getRids(calendar1)
            rids2, master2 = _getRids(calendar2)

            _addOverrides(calendar1, master1, rids2 - rids1)
            _addOverrides(calendar2, master2, rids1 - rids2)

        try:
            format = Calendar.sFormatJSON if is_json else Calendar.sFormatText

            resp_calendar = Calendar.parseData(respdata, format=format)
            removePropertiesParameters(resp_calendar)

            data_calendar = Calendar.parseData(data, format=format)
            removePropertiesParameters(data_calendar)

            reconcileRecurrenceOverrides(resp_calendar, data_calendar)

            respdata = resp_calendar.getText(includeTimezones=Calendar.NO_TIMEZONES, format=format)
            data = data_calendar.getText(includeTimezones=Calendar.NO_TIMEZONES, format=format)

            result = resp_calendar == data_calendar
            if not result:
                respdata2 = respdata.replace("\r\n ", "")
                data2 = data.replace("\r\n ", "").replace("urn:x-uid:", "urn:uuid:")
                result = respdata2 == data2

            if result:
                return True, ""
            else:
                error_diff = "\n".join([line for line in unified_diff(data.split("\n"), respdata.split("\n"))])
                return False, "        Response data does not exactly match file data%s" % (error_diff,)
        except Exception as e:
            return False, "        Response data is not calendar data: %s" % (e,)
