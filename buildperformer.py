#!/usr/bin/env python
#
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
#
# Generate performance data based on runs of different scripts.
#

import time
import performer

if __name__ == "__main__":

    results = []
    performs = (
        "scripts/buildperformance/get-small.xml",
        "scripts/buildperformance/get-large.xml",
        "scripts/buildperformance/put-small.xml",
        "scripts/buildperformance/put-large.xml",
    )
    
    for item in performs:
        pinfo, result = performer.runIt(item, silent=True)
        results.append((item[item.rfind("/")+1:item.rfind(".")], result[0][0], result[0][1], result[0][2]))
  
    print time.ctime(),
    for result in results:
        print "\t%s\t%.3f\t%.3f\t%.3f" % (result[0], result[1], result[2], result[3],),
    print ""
