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
Verifier that checks the response headers for a specific value.
"""

import re

class Verifier(object):
    
    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable
        # Split into header/value tuples
        testheader = args.get("header", [])[:]
        for i in range(len(testheader)):
            p = testheader[i]
            present = "single"
            if p[0] == "!":
                p = p[1:]
                present = "none"
            if p[0] == "*":
                p = p[1:]
                present = "multiple"
            if p.find("$") != -1:
                testheader[i] = (p.split("$", 1)[0], p.split("$", 1)[1], present,)
            else:
                testheader[i] = (p, None, present,)
        
        result = True
        resulttxt = ""
        for test in testheader:
            hdrs = response.msg.getheaders(test[0])
            if (hdrs is None or (len(hdrs) == 0)):
                if test[2] != "none":
                    result = False
                    if len(resulttxt):
                        resulttxt += "\n"
                    resulttxt += "        Missing Response Header: %s" % (test[0],)
                    continue
                else:
                    continue

            if (hdrs is not None) and (len(hdrs) != 0) and (test[2] == "none"):
                result = False
                if len(resulttxt):
                    resulttxt += "\n"
                resulttxt += "        Response Header was present one or more times: %s" % (test[0],)
                continue
               
            if (len(hdrs) != 1) and (test[2] == "single"):
                result = False
                if len(resulttxt):
                    resulttxt += "\n"
                resulttxt += "        Multiple Response Headers: %s" % (test[0],)
                continue
            
            if (test[1] is not None):
                matched = False
                for hdr in hdrs:
                     if (re.match(test[1], hdr) is not None):
                         matched = True
                         break
                        
                if not matched:
                    result = False
                    if len(resulttxt):
                        resulttxt += "\n"
                    resulttxt += "        Wrong Response Header Value: %s: %s" % (test[0], str(hdrs))

        return result, resulttxt
            
