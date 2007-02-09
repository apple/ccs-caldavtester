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
# Creates some test accounts on an OpenDirectory server for use with CalDAVTester
#
import time
import subprocess

from src.manager import manager
import getopt
import os
import signal
import sys

def usage():
    print """Usage: fsusage [options]
Options:
    -h       Print this help and exit
    -f file  pid file of caldavd server
"""

if __name__ == "__main__":

    options, args = getopt.getopt(sys.argv[1:], "f:")

    for option, value in options:
        if option == "-h":
            usage()
            sys.exit(0)
        elif option == "-f":
            pidfile = value
        else:
            print "Unrecognized option: %s" % (option,)
            usage()
            raise ValueError

    # First try to get pid of caldavd process
    fd = open(pidfile, "r")
    s = fd.read()
    pid = int(s)
    fd = None
    
    fd = open("temp", "w")
    cid = subprocess.Popen(["fs_usage", "-f", "filesys", "%s" %(pid,),], ).pid
    
    sname = "scripts/server/serverinfo.xml"
    pname = None
    fnames = ["performance/propfind/propfind-large.xml"]

    mgr = manager(level=manager.LOG_NONE)
    result, timing = mgr.runWithOptions(sname, pname, fnames, {})

    print cid
    #time.sleep(5)
    os.kill(cid, signal.SIGTERM)
