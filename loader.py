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
# Runs a series of test suites inb parallel using a thread pool
#

import cPickle as pickle
import getopt

import sys

from src.perfinfo import perfinfo

def usage():
    print """Usage: loader.py [options] <<script file>>
Options:
    -h       Print this help and exit
    -n       Do not print out results
    -o file  Write raw results to file
    -i num   Numeric offset for test counter
"""

def runIt(script, silent=False):

    pinfo = perfinfo.parseFile(script)

    pinfo.doStart(silent)

    allresults = pinfo.doLoadRamping()

    pinfo.doEnd(silent)
    
    return allresults

if __name__ == "__main__":

    output_file = None
    no_results = False
    offset = 0

    options, args = getopt.getopt(sys.argv[1:], "hno:i:")

    for option, value in options:
        if option == "-h":
            usage()
            sys.exit(0)
        elif option == "-n":
            no_results = True
        elif option == "-o":
            output_file = value
        elif option == "-i":
            offset = int(value)
        else:
            print "Unrecognized option: %s" % (option,)
            usage()
            raise ValueError

    perfinfoname = "scripts/performance/perfinfo.xml"
    if len(args) > 0:
        perfinfoname = args[0]

    allresults = perfinfo.runIt("load ramping", perfinfoname, silent=True, offset=offset)

    if output_file:
        fd = open(output_file, "w")
        fd.write(pickle.dumps(allresults))
        fd.close()

    if not no_results:
        # Print out averaged results.
        print "\n\nClients\tReqs/sec\tResponse (secs)"
        print "====================================================================="
        for raw, clients, reqs, resp in allresults:
            for x in raw:
                print x
            print "%d\t%.1f\t%.3f" % (clients, reqs, resp,)
