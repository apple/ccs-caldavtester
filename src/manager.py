##
# Copyright (c) 2006-2016 Apple Inc. All rights reserved.
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
Class to manage the testing process.
"""

from src.serverinfo import serverinfo

from importlib import import_module
from xml.etree.cElementTree import ElementTree
from xml.parsers.expat import ExpatError
import getopt
import os
import random
import src.xmlDefs
import sys
import time

# Exceptions

EX_INVALID_CONFIG_FILE = "Invalid Config File"
EX_FAILED_REQUEST = "HTTP Request Failed"


class manager:

    """
    Main class that runs test suites defined in an XML config file.
    """

    RESULT_OK = 0
    RESULT_FAILED = 1
    RESULT_ERROR = 2
    RESULT_IGNORED = 3

    def __init__(self, text=True):
        self.server_info = serverinfo()
        self.base_dir = ""
        self.data_dir = None
        self.pretest = None
        self.posttest = None
        self.tests = []
        self.textMode = text
        self.pid = 0
        self.memUsage = None
        self.randomSeed = None
        self.logFile = None
        self.digestCache = {}
        self.postgresLog = ""
        self.stoponfail = False
        self.print_request = False
        self.print_response = False
        self.print_request_response_on_error = False
        self.debug = False

        self.results = []
        self.totals = {
            self.RESULT_OK: 0,
            self.RESULT_FAILED: 0,
            self.RESULT_ERROR: 0,
            self.RESULT_IGNORED: 0
        }
        self.observers = []

    def logit(self, string):
        if self.logFile:
            self.logFile.write(string + "\n")
        print(string)

    def loadObserver(self, observer_name):
        module = import_module("src.observers." + observer_name)
        cl = getattr(module, "Observer")
        self.observers.append(cl(self))

    def message(self, message, *args, **kwargs):
        for observer in self.observers:
            observer.message(message, *args, **kwargs)

    def testProgress(self, count, total):
        results = {
            "count": count,
            "total": total,
        }
        self.message("testProgress", results)

    def testFile(self, name, details, result=None):
        self.results.append({
            "name": name,
            "details": details,
            "result": result,
            "tests": []
        })
        if result is not None:
            self.totals[result] += 1
        self.message("testFile", self.results[-1])
        return self.results[-1]["tests"]

    def testSuite(self, testfile, name, details, result=None):
        testfile.append({
            "name": name,
            "details": details,
            "result": result,
            "tests": []
        })
        if result is not None:
            self.totals[result] += 1
        self.message("testSuite", testfile[-1])
        return testfile[-1]["tests"]

    def testResult(self, testsuite, name, details, result, addons=None):
        result_details = {
            "name": name,
            "result": result,
            "details": details
        }
        if addons:
            result_details.update(addons)
        testsuite.append(result_details)
        self.totals[result] += 1
        self.message("testResult", testsuite[-1])

    def readXML(self, serverfile, testfiles, ssl, all, moresubs={}):

        self.message("trace", "Reading Server Info from \"{s}\"".format(s=serverfile))

        # Open and parse the server config file
        try:
            tree = ElementTree(file=serverfile)
        except ExpatError as e:
            raise RuntimeError("Unable to parse file '%s' because: %s" % (serverfile, e,))

        # Verify that top-level element is correct
        serverinfo_node = tree.getroot()
        if serverinfo_node.tag != src.xmlDefs.ELEMENT_SERVERINFO:
            raise EX_INVALID_CONFIG_FILE
        if not len(serverinfo_node):
            raise EX_INVALID_CONFIG_FILE
        self.server_info.parseXML(serverinfo_node)

        # Setup ssl stuff
        self.server_info.ssl = ssl
        self.server_info.port = self.server_info.sslport if ssl else self.server_info.nonsslport
        self.server_info.port2 = self.server_info.sslport2 if ssl else self.server_info.nonsslport2
        self.server_info.certdir = os.path.join(self.base_dir, self.server_info.certdir) if self.server_info.certdir else ""

        moresubs["$host:"] = "%s://%s" % (
            "https" if ssl else "http", self.server_info.host,
        )
        if (ssl and self.server_info.port != 443) or (not ssl and self.server_info.port != 80):
            moresubs["$host:"] += ":%d" % (self.server_info.port,)
        moresubs["$hostssl:"] = "https://%s" % (self.server_info.host,)
        if self.server_info.sslport != 443:
            moresubs["$hostssl:"] += ":%d" % (self.server_info.sslport,)

        moresubs["$host2:"] = "%s://%s" % (
            "https" if ssl else "http",
            self.server_info.host2,
        )
        if (ssl and self.server_info.port2 != 443) or (not ssl and self.server_info.port2 != 80):
            moresubs["$host2:"] += ":%d" % (self.server_info.port2,)
        moresubs["$hostssl2:"] = "https://%s" % (self.server_info.host2,)
        if self.server_info.sslport2 != 443:
            moresubs["$hostssl2:"] += ":%d" % (self.server_info.sslport2,)

        self.server_info.addsubs(moresubs)

        from src.caldavtest import caldavtest

        def _loadFile(fname, ignore_root=True):
            # Open and parse the config file
            try:
                tree = ElementTree(file=fname)
            except ExpatError as e:
                raise RuntimeError("Unable to parse file '%s' because: %s" % (fname, e,))
            caldavtest_node = tree.getroot()
            if caldavtest_node.tag != src.xmlDefs.ELEMENT_CALDAVTEST:
                if ignore_root:
                    self.message("trace", "Ignoring file \"{f}\" because it is not a test file".format(f=fname))
                    return None
                else:
                    raise EX_INVALID_CONFIG_FILE
            if not len(caldavtest_node):
                raise EX_INVALID_CONFIG_FILE

            self.message("Reading Test Details from \"{f}\"".format(f=fname))
            if self.base_dir:
                fname = fname[len(self.base_dir) + 1:]
            test = caldavtest(self, fname)
            test.parseXML(caldavtest_node)
            return test

        for ctr, testfile in enumerate(testfiles):
            self.message("load", testfile, ctr + 1, len(testfiles))

            # Open and parse the config file
            test = _loadFile(testfile)
            if test is None:
                continue

            # ignore if all mode and ignore-all is set
            if not all or not test.ignore_all:
                self.tests.append(test)

        if self.pretest is not None:
            self.pretest = _loadFile(self.pretest, False)
        if self.posttest is not None:
            self.posttest = _loadFile(self.posttest, False)

        self.message("load", None, ctr + 1, len(testfiles))

    def readCommandLine(self):
        sname = "scripts/server/serverinfo.xml"
        dname = "scripts/tests"
        fnames = []
        ssl = False
        all = False
        excludes = set()
        subdir = None
        pidfile = "../CalendarServer/logs/caldavd.pid"
        random_order = False
        random_seed = str(random.randint(0, 1000000))
        observer_names = []

        options, args = getopt.getopt(
            sys.argv[1:],
            "s:mo:x:",
            [
                "ssl",
                "all",
                "basedir=",
                "subdir=",
                "exclude=",
                "pretest=",
                "posttest=",
                "observer=",
                "pid=",
                "postgres-log=",
                "random",
                "random-seed=",
                "stop",
                "print-details-onfail",
                "always-print-request",
                "always-print-response",
                "debug"
            ],
        )

        # Process single options
        for option, value in options:
            if option == "-s":
                sname = value
            elif option == "-x":
                dname = value
            elif option == "--ssl":
                ssl = True
            elif option == "--all":
                all = True
            elif option == "--basedir":
                self.base_dir = value
                sname = os.path.join(self.base_dir, "serverinfo.xml")
                dname = os.path.join(self.base_dir, "tests")
                self.data_dir = os.path.join(self.base_dir, "data")

                # Also add parent to PYTHON path
                sys.path.append(os.path.dirname(self.base_dir))

            elif option == "--subdir":
                subdir = value + "/"
            elif option == "--exclude":
                excludes.add(value)
            elif option == "--pretest":
                self.pretest = value
            elif option == "--posttest":
                self.posttest = value
            elif option == "-m":
                self.memUsage = True
            elif option == "-o":
                self.logFile = open(value, "w")
            elif option == "--pid":
                pidfile = value
            elif option == "--observer":
                observer_names.append(value)
            elif option == "--postgres-log":
                self.postgresLog = value
            elif option == "--stop":
                self.stoponfail = True
            elif option == "--print-details-onfail":
                self.print_request_response_on_error = True
            elif option == "--always-print-request":
                self.print_request = True
            elif option == "--always-print-response":
                self.print_response = True
            elif option == "--random":
                random_order = True
            elif option == "--random-seed":
                random_seed = value
            elif option == "--debug":
                self.debug = True

        if all or not args:
            all_files = []
            for root, dirs, files in os.walk(dname):
                if not root.startswith("test"):
                    all_files.extend([os.path.join(root, name) for name in files])
            for file_ in all_files:
                if file_.endswith(".xml") and file_[len(dname) + 1:] not in excludes:
                    if subdir is None or file_[len(dname) + 1:].startswith(subdir):
                        fnames.append(file_)

        # Remove any server info file from files enumerated by --all
        fnames[:] = [x for x in fnames if (x != sname)]

        def _normPath(f):
            # paths starting with . or .. or /
            if f[0] in ('.', '/'):
                f = os.path.abspath(f)

                # remove unneeded leading path
                fsplit = f.split(dname)
                if 2 == len(fsplit):
                    f = dname + fsplit[1]

            # relative paths
            else:
                f = os.path.join(dname, f)
            return f

        # Process any file arguments as test configs
        for f in args:
            fnames.append(_normPath(f))

        if self.pretest is not None:
            self.pretest = _normPath(self.pretest)
        if self.posttest is not None:
            self.posttest = _normPath(self.posttest)

        # Randomize file list
        if random_order and len(fnames) > 1:
            random.seed(random_seed)
            random.shuffle(fnames)
            self.randomSeed = random_seed

        # Load observers
        for name in observer_names or ["log"]:
            self.loadObserver(name)

        self.readXML(sname, fnames, ssl, all)

        if self.memUsage:
            fd = open(pidfile, "r")
            s = fd.read()
            self.pid = int(s)

    def runAll(self):

        startTime = time.time()

        self.message("start")

        ok = 0
        failed = 0
        ignored = 0
        try:
            for ctr, test in enumerate(self.tests):
                if len(self.tests) > 1:
                    self.testProgress(ctr + 1, len(self.tests))
                if self.pretest is not None:
                    o, f, i = self.pretest.run()

                    # Always stop the tests if the pretest fails
                    if f != 0:
                        break

                o, f, i = test.run()
                ok += o
                failed += f
                ignored += i

                if failed != 0 and self.stoponfail:
                    break

                if self.posttest is not None:
                    o, f, i = self.posttest.run()

                    # Always stop the tests if the posttest fails
                    if f != 0:
                        break

        except:
            failed += 1
            import traceback
            traceback.print_exc()

        endTime = time.time()

        self.timeDiff = endTime - startTime
        self.message("finish")

        if self.logFile is not None:
            self.logFile.close()

        return failed, endTime - startTime

    def getMemusage(self):
        """

        @param pid: numeric pid of process to get memory usage for
        @type pid:  int
        @retrun:    tuple of (RSS, VSZ) values for the process
        """

        fd = os.popen("ps -l -p %d" % (self.pid,))
        data = fd.read()
        lines = data.split("\n")
        procdata = lines[1].split()
        return int(procdata[6]), int(procdata[7])

    def getDataPath(self, fpath):
        return os.path.join(self.data_dir, fpath) if self.data_dir else fpath
