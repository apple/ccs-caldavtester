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
    from pycalendar.vcard.card import Card
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
            files = map(lambda x: os.path.join(manager.data_dir, x), files)
        carddata = args.get("data", [])
        filters = args.get("filter", [])

        # Always remove these
        filters.extend(manager.server_info.addressdatafilters)

        # status code must be 200, 201, 207
        if response.status not in (200, 201, 207):
            return False, "        HTTP Status Code Wrong: %d" % (response.status,)

        # look for response data
        if not respdata:
            return False, "        No response body"

        # look for one file
        if len(files) != 1 and len(carddata) != 1:
            return False, "        No file to compare response to"

        # read in all data from specified file or use provided data
        if len(files):
            fd = open(files[0], "r")
            try:
                try:
                    data = fd.read()
                finally:
                    fd.close()
            except:  # noqa
                data = None
        else:
            data = carddata[0] if len(carddata) else None

        if data is None:
            return False, "        Could not read data file"

        data = manager.server_info.subs(data)

        def removePropertiesParameters(component):

            allProps = []
            for properties in component.getProperties().itervalues():
                allProps.extend(properties)
            for property in allProps:
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

        try:
            format = Card.sFormatJSON if is_json else Card.sFormatText

            resp_adbk = Card.parseData(respdata, format=format)
            removePropertiesParameters(resp_adbk)
            respdata = resp_adbk.getText(format=format)

            data_adbk = Card.parseData(data, format=format)
            removePropertiesParameters(data_adbk)
            data = data_adbk.getText(format=format)

            result = resp_adbk == data_adbk

            if result:
                return True, ""
            else:
                error_diff = "\n".join([line for line in unified_diff(data.split("\n"), respdata.split("\n"))])
                return False, "        Response data does not exactly match file data%s" % (error_diff,)
        except Exception as e:
            return False, "        Response data is not address data: %s" % (e,)
