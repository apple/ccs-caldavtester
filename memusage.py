#!/usr/bin/env python
#
##
# Copyright (c) 2007 Apple Inc. All rights reserved.
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
#
from src.manager import manager
import os
import sys
import getopt
 
# Runs a series of test suites a number of times and logs changes in process memory usage.
#

def getMemusage(pid):
    """
    
    @param pid: numeric pid of process to get memory usage for
    @type pid:  int
    @retrun:    tuple of (RSS, VSZ) values for the process
    """
    
    fd = os.popen("ps -l -p %d" %(pid,))
    data = fd.read()
    lines = data.split("\n")
    procdata = lines[1].split()
    return int(procdata[6]), int(procdata[7])

def usage():
    print """Usage: memusage.py [options]
Options:
    -h       Print this help and exit
    -p file  pid file of caldavd server
    -n num   number of times to execute each CalDAVTester script [1]
    -N num   number of times to execute all scripts [1]
    -m       monitor memory usage for each testsuite
    -x       suppress per-script usage
"""

if __name__ == "__main__":

    pidfile = "../CalendarServer/logs/caldavd.pid"
    num = 1
    loop = 1
    sname = "scripts/server/serverinfo.xml"
    pname = None
    dname = "scripts/tests"
    monitor = False
    suppress = False

    options, args = getopt.getopt(sys.argv[1:], "mN:n:p:x", [])

    for option, value in options:
        if option == "-h":
            usage()
            sys.exit(0)
        elif option == "-m":
            monitor = True
        elif option == "-N":
            loop = int(value)
        elif option == "-n":
            num = int(value)
        elif option == "-p":
            pidfile = value
        elif option == "-x":
            suppress = True
        else:
            print "Unrecognized option: %s" % (option,)
            usage()
            raise ValueError

    # First try to get pid of caldavd process
    fd = open(pidfile, "r")
    s = fd.read()
    pid = int(s)

    fnames = []
    fnames[:] = args
    if fnames:
        fnames = [os.path.join(dname, file) for file in fnames]
    else:
        files = os.listdir(dname)
        for file in files:
            if file.endswith(".xml"):
                fnames.append(os.path.join(dname, file))

        # Remove any server info file from files enuerated by --all
        fnames[:] = [x for x in fnames if (x != sname) and (not pname or (x != pname))]

    # Get initial memory usage for later comparison
    overall_start_usage = getMemusage(pid)

    for looper in range(loop):
        print "-Overall loop: %d of %d" % (looper + 1, loop,)
        data = []
        for ctr, f in enumerate(fnames):
            
            print "--Script: %d of %d" % (ctr + 1, len(fnames),)
    
            # Get initial memory usage for later comparison
            start_usage = getMemusage(pid)
            
            # Now run caldav tester scripts a number of times
            for loopy in range(num):
                if num > 1:
                    print "---Loop %d of %d" % (loopy + 1, num,)
                tester = manager()
                if suppress:
                    tester.logLevel = manager.LOG_NONE
                else:
                    tester.logLevel = manager.LOG_LOW
                tester.runWithOptions(sname, pname, [f], {}, pid=pid, memUsage=monitor)
            
            # Get final memory usage
            end_usage = getMemusage(pid)
            
            data.append((f, start_usage, end_usage,))
        
        if not suppress:
            print ""
            print "RESULTS"
            print ""
            for f, start_usage, end_usage in data:
                # Print out the diff
                print "*** Memory Usage for test: %s ***" % (f,)
                print "".join([s.ljust(15) for s in ("", "RSS", "VSZ")])
                print "".join([s.ljust(15) for s in ("-"*15, "-"*15, "-"*15)])
                print "".join([s.ljust(15) for s in ("Start:", str(start_usage[1]), str(start_usage[0]))])
                print "".join([s.ljust(15) for s in ("End:", str(end_usage[1]), str(end_usage[0]))])
                print "".join([s.ljust(15) for s in ("Change:", str(end_usage[1] - start_usage[1]), str(end_usage[0] - start_usage[0]))])
                print "".join([s.ljust(15) for s in ("%Change:", str(((end_usage[1] - start_usage[1]) * 100)/start_usage[1]), str(((end_usage[0] - start_usage[0]) * 100)/start_usage[0]))])
                print ""
        
    # Get final memory usage
    overall_end_usage = getMemusage(pid)

    print "*** Overall Memory Usage ***"
    print "".join([s.ljust(15) for s in ("", "RSS", "VSZ")])
    print "".join([s.ljust(15) for s in ("-"*15, "-"*15, "-"*15)])
    print "".join([s.ljust(15) for s in ("Start:", str(overall_start_usage[1]), str(overall_start_usage[0]))])
    print "".join([s.ljust(15) for s in ("End:", str(overall_end_usage[1]), str(overall_end_usage[0]))])
    print "".join([s.ljust(15) for s in ("Change:", str(overall_end_usage[1] - overall_start_usage[1]), str(overall_end_usage[0] - overall_start_usage[0]))])
    print "".join([s.ljust(15) for s in ("%Change:", str(((overall_end_usage[1] - overall_start_usage[1]) * 100)/overall_start_usage[1]), str(((overall_end_usage[0] - overall_start_usage[0]) * 100)/overall_start_usage[0]))])
    print ""
