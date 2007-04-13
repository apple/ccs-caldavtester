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
import time

import os
import sys

def usage():
    print """Usage: multiload.py [options] <<script file>>
Options:
    -h       Print this help and exit
    -p num   Number of sub-process to create
"""

if __name__ == "__main__":

    processes = 1

    options, args = getopt.getopt(sys.argv[1:], "hp:")

    for option, value in options:
        if option == "-h":
            usage()
            sys.exit(0)
        elif option == "-p":
            processes = int(value)
        else:
            print "Unrecognized option: %s" % (option,)
            usage()
            raise ValueError

    perfinfoname = "scripts/performance/perfinfo.xml"
    if len(args) > 0:
        perfinfoname = args[0]

    pids = []
    offset = 50
    for i in range(processes):
        output_file = "tmp.output.%s" % (i,)
        if i == 0:
            pids.append(os.spawnlp(os.P_NOWAIT, "python", "python", "loader.py", "-n", "-o", output_file, perfinfoname))
        else:
            pids.append(os.spawnlp(os.P_NOWAIT, "python", "python", "loader.py", "-n", "-o", output_file, "-i", "%d" % (i * offset), perfinfoname))
        print "Created pid %s" % (pids[-1],)
    
    while sum(pids) != 0:
        try:
            for i, pid in enumerate(pids):
                wpid, sts = os.waitpid(pid, os.WNOHANG)
            if wpid and os.WIFEXITED(sts):
                pids[i] = 0
            time.sleep(10)
        except OSError:
            break

    print "All child process complete. Aggregating data now..."

    raw = []
    clients = []
    for i in range(processes):
        output_file = "tmp.output.%s" % (i,)
        fd = open(output_file, "r")
        s = fd.read()
        fd.close()
        result = pickle.loads(s)
        if len(raw) == 0:
            for j in range(len(result)):
                raw.append([])
                clients.append(result[j][1])
        for j in range(len(result)):
            raw[j].append(result[j][0])
    
    allresults = []
    for ctr, items in enumerate(raw):
        aggregate = {}
        for item in items:
            for time, resp, num in item:
                aggregate.setdefault(time, []).append((resp, num))
        
        averaged = {}
        for key, values in aggregate.iteritems():
            average = 0.0
            nums = 0
            for resp, num in values:
                average += resp * num
                nums += num
            average /= nums
            averaged[key] = (average, nums,)
    
        avkeys = averaged.keys()
        avkeys.sort()
        avkeys = avkeys[len(avkeys)/3:-len(avkeys)/3]
        rawresults = []
        average_time = 0.0
        average_clients = 0.0
        for i in avkeys:
            rawresults.append((i, averaged[i][0], averaged[i][1]))
            average_time += averaged[i][0]
            average_clients += averaged[i][1]
        average_time /= len(avkeys)
        average_clients /= len(avkeys)
    
        allresults.append((clients[ctr] * processes, average_clients, average_time,))
        
    # Print out averaged results.
    print "\n\nClients\tReqs/sec\tResponse (secs)"
    print "====================================================================="
    for clients, reqs, resp in allresults:
        print "%d\t%.1f\t%.3f" % (clients, reqs, resp,)
