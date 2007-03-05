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

import performer
import sys

def human_readable(item, avg, stddev, total):
     print "\t%s\t%.3f\t%.3f\t%.3f" % (item, avg, stddev, total)

def main(logger):

    performs = (
        "scripts/buildperformance/get-small.xml",
        "scripts/buildperformance/get-large.xml",
        "scripts/buildperformance/put-small.xml",
        "scripts/buildperformance/put-large.xml",
    )
    
    for item in performs:
        pinfo, result = performer.runIt(item, silent=True)
        if result[0][0] == -1.0 or result[0][1] == -1.0 or result[0][2] == -1.0:
            print "Failed: got result -1.0 for test script %s" % (item,)
            sys.exit(1)
        logger(item[item.rfind("/")+1:item.rfind(".")], result[0][0], result[0][1], result[0][2])
  
if __name__ == "__main__":
    main(human_readable)
