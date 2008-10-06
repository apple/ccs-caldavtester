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
##
#
# Generates fs_usage counts for CalDAVTester script runs.
#

from src.manager import manager
import getopt
import os
import signal
import subprocess
import sys
import time

def usage():
    print """Usage: fsusage [options]
Options:
    -h       Print this help and exit
    -f file  pid file of caldavd server
"""

def getFSUsage(count, testscript, runs, pid, sname):
    tmpfile = "temp.fsusage.%02d" % (count,)
    fd = open(tmpfile, "w")
    cid = subprocess.Popen(["fs_usage", "-f", "filesys", "%s" %(pid,),], stdout=fd, stderr=fd).pid
    
    time.sleep(5)
    
    pname = None
    fnames = [testscript]

    mgr = manager(level=manager.LOG_NONE)
    _ignore_result, _ignore_timing = mgr.runWithOptions(sname, pname, fnames, {})

    os.kill(cid, signal.SIGTERM)

    fd = open(tmpfile, "r")
    ctr = 0
    for _ignore_line in fd:
        ctr += 1

    return ctr / runs

if __name__ == "__main__":

    pidfile = "../CalendarServer/logs/caldavd.pid"
    scriptsfile = "scripts/server/serverinfo.xml"
    options, args = getopt.getopt(sys.argv[1:], "f:s:")

    for option, value in options:
        if option == "-h":
            usage()
            sys.exit(0)
        elif option == "-f":
            pidfile = value
        elif option == "-s":
            scriptsfile = value
        else:
            print "Unrecognized option: %s" % (option,)
            usage()
            raise ValueError

    # First try to get pid of caldavd process
    fd = open(pidfile, "r")
    s = fd.read()
    pid = int(s)
    fd = None
    
    tests = (
        ("performance/put/put-small.xml", 10, "put-small",),
        ("performance/put/put-large.xml", 10, "put-large",),
        ("performance/get/get-small.xml", 10, "get-small",),
        ("performance/get/get-large.xml", 10, "get-large",),
        ("performance/propfind/propfind-ctag.xml", 10, "propfind-ctag",),
        ("performance/propfind/propfind-small.xml", 10, "propfind-small",),
        ("performance/propfind/propfind-medium.xml", 10, "propfind-medium",),
        ("performance/propfind/propfind-large.xml", 10, "propfind-large",),
    )
    
    result = []
    for ctr, test in enumerate(tests):
        print "%s\t%s" % (test[2], getFSUsage(ctr, test[0], test[1], pid, scriptsfile),)
