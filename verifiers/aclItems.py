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
Verifier that checks a propfind response to make sure that the specified ACL privileges
are available for the currently authenticated user.
"""

from xml.dom.minicompat import NodeList
from xml.dom.minidom import Element
from xml.dom.minidom import Node
import xml.dom.minidom

class Verifier(object):
    
    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable

        def ElementsByName(parent, nsURI, localName):
            rc = NodeList()
            for node in parent.childNodes:
                if node.nodeType == Node.ELEMENT_NODE:
                    if ((localName == "*" or node.localName == localName) and
                        (nsURI == "*" or node.namespaceURI == nsURI)):
                        rc.append(node)
            return rc

        granted = args.get("granted", [])
        denied = args.get("denied", [])
        
        # Process the multistatus response, extracting all current-user-privilege-set elements
        # and check to see that each required privilege is present, or that denied ones are not.
        
        # Must have MULTISTATUS response code
        if response.status != 207:
            return False, "           HTTP Status for Request: %d\n" % (response.status,)
            
        doc = xml.dom.minidom.parseString( respdata )
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

            # Get all privileges
            granted_privs = []
            privset = response.getElementsByTagNameNS("DAV:", "current-user-privilege-set")
            for props in privset:
                # Determine status for this propstat
                privileges = ElementsByName(props, "DAV:", "privilege")
                for privilege in privileges:
                    for child in privilege._get_childNodes():
                        if isinstance(child, Element):
                            qname = (child.namespaceURI, child.localName)
                            fqname = qname[0] + qname[1]
                            granted_privs.append( fqname )
    
            granted_result_set = set( granted_privs )
            granted_test_set = set( granted )
            denied_test_set = set( denied )
            
            # Now do set difference
            granted_missing = granted_test_set.difference( granted_result_set )
            denied_present = granted_result_set.intersection( denied_test_set )
            
            if len( granted_missing ) + len( denied_present ) != 0:
                if len( granted_missing ) != 0:
                    l = list( granted_missing )
                    resulttxt += "        Missing privileges not granted for %s:" % href
                    for i in l:
                        resulttxt += " " + str(i) 
                    resulttxt += "\n"
                if len( denied_present ) != 0:
                    l = list( denied_present )
                    resulttxt += "        Available privileges that should be denied for %s:" % href
                    for i in l:
                        resulttxt += " " + str(i) 
                    resulttxt += "\n"
                result = False
            
        return result, resulttxt
