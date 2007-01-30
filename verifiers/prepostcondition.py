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
Verifier that checks the response for a pre/post-condition <DAV:error> result.
"""
from xml.dom.minidom import Element

import xml.dom.minidom

class Verifier(object):
    
    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable
        # If no status veriffication requested, then assume all 2xx codes are OK
        teststatus = args.get("error", [])
        
        # status code must be 403 or 409 as per rfc3253 section 1.6
        if response.status not in [403, 409]:
            return False, "        HTTP Status Code Wrong: %d" % (response.status,)
        
        # look for pre-condition data
        if not respdata:
            return False, "        No pre/post condition response body"
            
        try:
            doc = xml.dom.minidom.parseString( respdata )
        except Exception, ex:
            return False, "        Could not parse XML: %s" %(ex,)
        error = doc._get_documentElement()
        errorName = (error.namespaceURI, error.localName)

        if errorName != ("DAV:", "error"):
            return False, "        Missing <DAV:error> element in response"

        # Make a set of expected pre/post condition elements
        expected = set(teststatus)
        got = set()
        for child in error._get_childNodes():
            if isinstance(child, Element):
                qname = (child.namespaceURI, child.localName)
                fqname = qname[0] + qname[1]
                got.add(fqname)
        
        missing = expected.difference(got)
        extras = got.difference(expected)
        
        err_txt = ""
        if len(missing):
            err_txt += "        Items not returned in error: element %s" % str(missing)
        if len(extras):
            if len(err_txt):
                err_txt += "\n"
            err_txt += "        Unexpected items returned in error element: %s" % str(extras)
        if len(missing) or len(extras):
            return False, err_txt

        return True, ""
            
