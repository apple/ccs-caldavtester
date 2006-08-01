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
Verifier that chec ks the response status code for a specific value.
"""

class Verifier(object):
    
    def verify(self, uri, response, respdata, args): #@UnusedVariable
        # If no status veriffication requested, then assume all 2xx codes are OK
        teststatus = args.get("status", ["2xx"])
        
        for test in teststatus:
            if test[1:3] == "xx":
                test = int(test[0])
            else:
                test = int(test)
            if test < 100:
                result = ((response.status / 100) == test)
            else:
                result = (response.status == test)
            if result: return True, ""
        
        return False, "        HTTP Status Code Wrong: %d" % (response.status,)
            
