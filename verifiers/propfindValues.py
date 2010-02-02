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
Verifier that checks a propfind response for regex matches to property values.
"""

import re

from xml.dom.minidom import Element
import xml.dom.minidom

from utilities.xmlutils import ElementsByName

class Verifier(object):
    
    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable

        # If no status verification requested, then assume all 2xx codes are OK
        ignores = args.get("ignore", [])

        # Get property arguments and split on $ delimited for name, value tuples
        testprops = args.get("props", [])
        props_match = []
        for i in range(len(testprops)):
            p = testprops[i]
            if (p.find("$") != -1):
                if p.find("$") != len(p) - 1:
                    props_match.append((p.split("$")[0], p.split("$")[1], True))
                else:
                    props_match.append((p.split("$")[0], "", True))
            elif (p.find("!") != -1):
                if  p.find("!") != len(p) - 1:
                    props_match.append((p.split("!")[0], p.split("!")[1], False))
                else:
                    props_match.append((p.split("!")[0], "", False))

        # Process the multistatus response, extracting all hrefs
        # and comparing with the properties defined for this test. Report any
        # mismatches.
        
        # Must have MULTISTATUS response code
        if response.status != 207:
            return False, "           HTTP Status for Request: %d\n" % (response.status,)
        
        try:
            doc = xml.dom.minidom.parseString( respdata )
        except:
            return False, "           Could not parse proper XML response\n"
                
        result = True
        resulttxt = ""
        for response in doc.getElementsByTagNameNS( "DAV:", "response" ):

            # Get href for this response
            href = ElementsByName(response, "DAV:", "href")
            if len(href) != 1:
                return False, "           Wrong number of DAV:href elements\n"
            if href[0].firstChild is not None:
                href = href[0].firstChild.data
            else:
                href = ""
            if href in ignores:
                continue
            
            # Get all property status
            ok_status_props = {}
            propstatus = ElementsByName(response, "DAV:", "propstat")
            for props in propstatus:
                # Determine status for this propstat
                status = ElementsByName(props, "DAV:", "status")
                if len(status) == 1:
                    statustxt = status[0].firstChild.data
                    status = False
                    if statustxt.startswith("HTTP/1.1 ") and (len(statustxt) >= 10):
                        status = (statustxt[9] == "2")
                else:
                    status = False
                
                # Get properties for this propstat
                prop = ElementsByName(props, "DAV:", "prop")
                if len(prop) != 1:
                    return False, "           Wrong number of DAV:prop elements\n"

                def _removeEmptyNodes(node):
                    for child in tuple(node._get_childNodes()):
                        temp = child.toprettyxml("", "")
                        temp = temp.strip()
                        if not temp:
                            node.removeChild(child)
                        else:
                            _removeEmptyNodes(child)
                    
                for child in prop[0]._get_childNodes():
                    if isinstance(child, Element):
                        qname = (child.namespaceURI, child.localName)
                        fqname = qname[0] + qname[1]
                        if child.firstChild is not None:
                            # Copy sub-element data as text into one long string and strip leading/trailing space
                            _removeEmptyNodes(child)
                            value = ""
                            for p in child._get_childNodes():
                                value += p.toprettyxml("", "")
                        else:
                            value = None
                        
                        if status:
                            ok_status_props[fqname] = value
    
            # Look at each property we want to test and see if present
            for propname, value, match in props_match:
                if propname not in ok_status_props:
                    resulttxt += "        Items not returned in report (OK) for %s: %s\n" % (href, propname,)
                    result = False
                    continue
                matched = re.match(value, ok_status_props[propname])
                if match and not matched:
                    resulttxt += "        Items not matching for %s: %s %s\n" % (href, propname, ok_status_props[propname])
                    result = False
                elif not match and matched:
                    resulttxt += "        Items incorrectly match for %s: %s %s\n" % (href, propname, ok_status_props[propname])
                    result = False

        return result, resulttxt
