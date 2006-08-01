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
Verifier that checks the response headers for a specific value.
"""

import re

class Verifier(object):
    
    def verify(self, uri, response, respdata, args): #@UnusedVariable
        # Split into header/value tuples
        testheader = args.get("header", [])
        for i in range(len(testheader)):
            p = testheader[i]
            present = True
            if p[0] == "!":
                p = p[1:]
                present = False
            if p.find("$") != -1:
                testheader[i] = (p.split("$", 1)[0], p.split("$", 1)[1], present,)
            else:
                testheader[i] = (p, None, present,)
        
        result = True
        resulttxt = ""
        for test in testheader:
            hdrs = response.msg.getheaders(test[0])
            if (hdrs is None or (len(hdrs) == 0)):
                if test[2]:
                    result = False
                    if len(resulttxt):
                        resulttxt += "\n"
                    resulttxt += "        Missing Response Header: %s" % (test[0],)
                    continue
                else:
                    continue

            if (hdrs is not None) and (len(hdrs) != 0) and not test[2]:
                result = False
                if len(resulttxt):
                    resulttxt += "\n"
                resulttxt += "        Response Header was present one or more times: %s" % (test[0],)
                continue
               
            if len(hdrs) != 1:
                result = False
                if len(resulttxt):
                    resulttxt += "\n"
                resulttxt += "        Multiple Response Headers: %s" % (test[0],)
                continue
            if (test[1] is not None) and (re.match(test[1], hdrs[0]) is None):
                result = False
                if len(resulttxt):
                    resulttxt += "\n"
                resulttxt += "        Wrong Response Header Value: %s: %s" % (test[0], hdrs[0])
                continue

        return result, resulttxt
            
