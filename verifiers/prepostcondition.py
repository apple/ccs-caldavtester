##
# Copyright (c) 2006 Apple Computer, Inc. All rights reserved.
#
# This file contains Original Code and/or Modifications of Original Code
# as defined in and that are subject to the Apple Public Source License
# Version 2.0 (the 'License'). You may not use this file except in
# compliance with the License. Please obtain a copy of the License at
# http://www.opensource.apple.com/apsl/ and read it before using this
# file.
#
# The Original Code and all software distributed under the License are
# distributed on an 'AS IS' basis, WITHOUT WARRANTY OF ANY KIND, EITHER
# EXPRESS OR IMPLIED, AND APPLE HEREBY DISCLAIMS ALL SUCH WARRANTIES,
# INCLUDING WITHOUT LIMITATION, ANY WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE, QUIET ENJOYMENT OR NON-INFRINGEMENT.
# Please see the License for the specific language governing rights and
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
    
    def verify(self, uri, response, respdata, args): #@UnusedVariable
        # If no status veriffication requested, then assume all 2xx codes are OK
        teststatus = args.get("error", [])
        
        # status code must be 403 or 409 as per rfc3253 section 1.6
        if response.status not in [403, 409]:
            return False, "        HTTP Status Code Wrong: %d" % (response.status,)
        
        # look for pre-condition data
        if not respdata:
            return False, "        No pre/post condition response body"
            
        doc = xml.dom.minidom.parseString( respdata )
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
            
