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
Class to encapsulate a single caldav test run.
"""

from io import BytesIO
try:
    # Treat pycalendar as optional
    from pycalendar.icalendar.calendar import Calendar
except ImportError:
    pass
from src.httpshandler import SmartHTTPConnection
from src.jsonPointer import JSONMatcher
from src.manager import manager
from src.request import data, pause
from src.request import request
from src.request import stats
from src.testsuite import testsuite
from src.xmlUtils import nodeForPath, xmlPathSplit
from xml.etree.cElementTree import ElementTree, tostring
import subprocess
from http.client import HTTPConnection
import json
import os
from email.utils import parsedate
import socket
import src.xmlDefs
import sys
import time
import traceback
from urllib.parse import quote, urlparse, urlunparse
"""
Patch the HTTPConnection.send to record full request details
"""

HTTPConnection._send = HTTPConnection.send


def recordRequestHeaders(self, data):
    if not hasattr(self, "requestData"):
        self.requestData = ""
    self.requestData += str
    HTTPConnection._send(self, data)


HTTPConnection.send = recordRequestHeaders


def getVersionStringFromResponse(response):

    if response.version == 9:
        return "HTTP/0.9"
    elif response.version == 10:
        return "HTTP/1.0"
    elif response.version == 11:
        return "HTTP/1.1"
    else:
        return "HTTP/?.?"


class caldavtest(object):

    def __init__(self, manager, name):
        self.manager = manager
        self.name = name
        self.description = ""
        self.require_features = set()
        self.exclude_features = set()
        self.ignore_all = False
        self.only = False
        self.start_requests = []
        self.end_requests = []
        self.end_deletes = []
        self.suites = []
        self.grabbedlocation = None
        self.previously_found = set()
        self.uidmaps = {}

    def missingFeatures(self):
        return self.require_features - self.manager.server_info.features

    def excludedFeatures(self):
        return self.exclude_features & self.manager.server_info.features

    def run(self):
        if len(self.missingFeatures()) != 0:
            self.manager.testFile(
                self.name, "Missing features: %s" % (", ".join(sorted(self.missingFeatures()),)), manager.RESULT_IGNORED
            )
            return 0, 0, 1
        if len(self.excludedFeatures()) != 0:
            self.manager.testFile(
                self.name, "Excluded features: %s" % (", ".join(sorted(self.excludedFeatures()),)),
                manager.RESULT_IGNORED
            )
            return 0, 0, 1

        # Always need a new set of UIDs for the entire test
        uids = self.manager.server_info.newUIDs()
        for uid, uidname in uids:
            self.uidmaps[uid] = "{u} - {n}".format(u=uidname, n=self.name)

        self.only = any([suite.only for suite in self.suites])
        try:
            result = self.dorequests(
                "Start Requests...", self.start_requests, False, True, label="%s | %s" % (self.name, "START_REQUESTS")
            )
            if not result:
                self.manager.testFile(self.name, "Start items failed - tests will not be run.", manager.RESULT_ERROR)
                ok, failed, ignored = (
                    0,
                    1,
                    0,
                )
            else:
                ok, failed, ignored = self.run_tests(label=self.name)
            self.doenddelete("Deleting Requests...", label="%s | %s" % (self.name, "END_DELETE"))
            self.dorequests("End Requests...", self.end_requests, False, label="%s | %s" % (self.name, "END_REQUESTS"))
            return ok, failed, ignored
        except socket.error as msg:
            self.manager.testFile(self.name, "SOCKET ERROR: %s" % (msg,), manager.RESULT_ERROR)
            return 0, 1, 0
        except Exception as e:
            self.manager.testFile(self.name, "FATAL ERROR: %s" % (e,), manager.RESULT_ERROR)
            if self.manager.debug:
                traceback.print_exc()
            return 0, 1, 0

    def run_tests(self, label=""):
        ok = 0
        failed = 0
        ignored = 0
        testfile = self.manager.testFile(self.name, self.description)
        for suite in self.suites:
            o, f, i = self.run_test_suite(testfile, suite, label="%s | %s" % (label, suite.name))
            ok += o
            failed += f
            ignored += i
        return (ok, failed, ignored)

    def run_test_suite(self, testfile, suite, label=""):
        result_name = suite.name
        ok = 0
        failed = 0
        ignored = 0
        postgresCount = None
        if self.only and not suite.only or suite.ignore:
            self.manager.testSuite(testfile, result_name, "    Deliberately ignored", manager.RESULT_IGNORED)
            ignored = len(suite.tests)
        elif len(suite.missingFeatures()) != 0:
            self.manager.testSuite(
                testfile, result_name, "    Missing features: %s" % (", ".join(sorted(suite.missingFeatures())),),
                manager.RESULT_IGNORED
            )
            ignored = len(suite.tests)
        elif len(suite.excludedFeatures()) != 0:
            self.manager.testSuite(
                testfile, result_name, "    Excluded features: %s" % (", ".join(sorted(suite.excludedFeatures())),),
                manager.RESULT_IGNORED
            )
            ignored = len(suite.tests)
        else:
            postgresCount = self.postgresInit()
            if self.manager.memUsage:
                start_usage = self.manager.getMemusage()
            etags = {}
            only_tests = any([test.only for test in suite.tests])
            testsuite = self.manager.testSuite(testfile, result_name, "")
            uids = suite.aboutToRun()
            for uid, uidname in uids:
                self.uidmaps[uid] = "{u} - {l}".format(u=uidname, l=label)
            for test in suite.tests:
                result = self.run_test(testsuite, test, etags, only_tests, label="%s | %s" % (label, test.name))
                if result == "t":
                    ok += 1
                elif result == "f":
                    failed += 1
                else:
                    ignored += 1

            if self.manager.memUsage:
                end_usage = self.manager.getMemusage()
                usage0 = ((end_usage[0] - start_usage[0]) * 100) / start_usage[0]
                usage1 = ((end_usage[1] - start_usage[1]) * 100) / start_usage[1]
                self.manager.message("trace", "    Mem. Usage: RSS=%s%% VSZ=%s%%" % (str(usage1), str(usage0)))

        self.manager.message("trace", "  Suite Results: %d PASSED, %d FAILED, %d IGNORED\n" % (ok, failed, ignored))
        if postgresCount is not None:
            self.postgresResult(postgresCount, indent=4)
        return (ok, failed, ignored)

    def run_test(self, testsuite, test, etags, only, label=""):
        if test.ignore or only and not test.only:
            self.manager.testResult(testsuite, test.name, "      Deliberately ignored", manager.RESULT_IGNORED)
            return "i"
        elif len(test.missingFeatures()) != 0:
            self.manager.testResult(
                testsuite, test.name, "      Missing features: %s" % (", ".join(sorted(test.missingFeatures())),),
                manager.RESULT_IGNORED
            )
            return "i"
        elif len(test.excludedFeatures()) != 0:
            self.manager.testResult(
                testsuite, test.name, "      Excluded features: %s" % (", ".join(sorted(test.excludedFeatures())),),
                manager.RESULT_IGNORED
            )
            return "i"
        else:
            result = True
            resulttxt = ""
            postgresCount = self.postgresInit()
            if test.stats:
                reqstats = stats()
            else:
                reqstats = None
            for ctr in range(test.count):
                for req_count, req in enumerate(test.requests):
                    t = time.time(
                    ) + (self.manager.server_info.waitsuccess if getattr(req, "wait_for_success", False) else 100)
                    while t > time.time():
                        failed = False
                        if getattr(req, "iterate_data", False):
                            if not req.hasNextData():
                                self.manager.testResult(
                                    testsuite, test.name, "      No iteration data - ignored", manager.RESULT_IGNORED
                                )
                                return "i"
                            while req.getNextData():
                                result, resulttxt, _ignore_response, _ignore_respdata = self.dorequest(
                                    req,
                                    test.details,
                                    True,
                                    False,
                                    reqstats,
                                    etags=etags,
                                    label="%s | #%s" % (
                                        label,
                                        req_count + 1,
                                    ),
                                    count=ctr + 1
                                )
                                if not result:
                                    failed = True
                                    break
                        else:
                            result, resulttxt, _ignore_response, _ignore_respdata = self.dorequest(
                                req,
                                test.details,
                                True,
                                False,
                                reqstats,
                                etags=etags,
                                label="%s | #%s" % (
                                    label,
                                    req_count + 1,
                                ),
                                count=ctr + 1
                            )
                            if not result:
                                failed = True

                        if not failed or not req.wait_for_success:
                            break
                    if failed:
                        break

            addons = {}
            if len(resulttxt) > 0:
                self.manager.message("trace", resulttxt)
            if result and test.stats:
                self.manager.message("trace", "    Total Time: %.3f secs" % (reqstats.totaltime,), indent=8)
                self.manager.message(
                    "trace", "    Average Time: %.3f secs" % (reqstats.totaltime / reqstats.count,), indent=8
                )
                addons["timing"] = {
                    "total": reqstats.totaltime,
                    "average": reqstats.totaltime / reqstats.count,
                }
            self.postgresResult(postgresCount, indent=8)
            self.manager.testResult(
                testsuite, test.name, resulttxt, manager.RESULT_OK if result else manager.RESULT_FAILED, addons
            )
            return ["f", "t"][result]

    def dorequests(self, description, list, doverify=True, forceverify=False, label="", count=1):
        if len(list) == 0:
            return True
        self.manager.message("trace", "Start: " + description)
        for req_count, req in enumerate(list):
            result, resulttxt, _ignore_response, _ignore_respdata = self.dorequest(
                req, False, doverify, forceverify, label="%s | #%s" % (label, req_count + 1), count=count
            )
            if not result:
                resulttxt += "\nFailure during multiple requests #%d out of %d, request=%s" % (
                    req_count + 1, len(list), str(req)
                )
                break
        self.manager.message(
            "trace", "{name:<60}{value:>10}".format(name="End: " + description, value=["[FAILED]", "[OK]"][result])
        )
        if len(resulttxt) > 0:
            self.manager.message("trace", resulttxt)
        return result

    def doget(self, original_request, resource, label=""):
        req = request(self.manager)
        req.method = "GET"
        req.host = original_request.host
        req.port = original_request.port
        req.ruris.append(resource[0])
        req.ruri = resource[0]
        if len(resource[1]):
            req.user = resource[1]
        if len(resource[2]):
            req.pswd = resource[2]
        _ignore_result, _ignore_resulttxt, response, respdata = self.dorequest(req, False, False, label=label)
        if response.status / 100 != 2:
            return False, None

        return True, respdata

    def dofindall(self, original_request, collection, label=""):
        hrefs = []
        req = request(self.manager)
        req.method = "PROPFIND"
        req.host = original_request.host
        req.port = original_request.port
        req.ruris.append(collection[0])
        req.ruri = collection[0]
        req.headers["Depth"] = "1"
        if len(collection[1]):
            req.user = collection[1]
        if len(collection[2]):
            req.pswd = collection[2]
        req.data = data(self.manager)
        req.data.value = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
<D:getetag/>
</D:prop>
</D:propfind>
"""
        req.data.content_type = "text/xml"
        result, _ignore_resulttxt, response, respdata = self.dorequest(req, False, False, label=label)
        if result and (response is not None) and (response.status == 207) and (respdata is not None):
            try:
                tree = ElementTree(file=BytesIO(respdata))
            except Exception:
                return ()

            request_uri = req.getURI(self.manager.server_info)
            for response in tree.findall("{DAV:}response"):

                # Get href for this response
                href = response.findall("{DAV:}href")
                if len(href) != 1:
                    return False, "           Wrong number of DAV:href elements\n"
                href = href[0].text
                if href != request_uri:
                    hrefs.append((href, collection[1], collection[2]))
        return hrefs

    def dodeleteall(self, original_request, deletes, label=""):
        if len(deletes) == 0:
            return True
        for deleter in deletes:
            req = request(self.manager)
            req.method = "DELETE"
            req.host = original_request.host
            req.port = original_request.port
            req.ruris.append(deleter[0])
            req.ruri = deleter[0]
            if len(deleter[1]):
                req.user = deleter[1]
            if len(deleter[2]):
                req.pswd = deleter[2]
            _ignore_result, _ignore_resulttxt, response, _ignore_respdata = self.dorequest(
                req, False, False, label=label
            )
            if response.status / 100 != 2:
                return False

        return True

    def dofindnew(self, original_request, collection, label="", other=False):
        hresult = ""

        uri = collection[0]
        if other:
            uri = self.manager.server_info.extrasubs(uri)
            skip = uri
            uri = "/".join(uri.split("/")[:-1]) + "/"
        else:
            skip = None
        possible_matches = set()
        req = request(self.manager)
        req.method = "PROPFIND"
        req.host = original_request.host
        req.port = original_request.port
        req.ruris.append(uri)
        req.ruri = uri
        req.headers["Depth"] = "1"
        if len(collection[1]):
            req.user = collection[1]
        if len(collection[2]):
            req.pswd = collection[2]
        req.data = data(self.manager)
        req.data.value = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
<D:getetag/>
<D:getlastmodified/>
</D:prop>
</D:propfind>
"""
        req.data.content_type = "text/xml"
        result, _ignore_resulttxt, response, respdata = self.dorequest(
            req, False, False, label="%s | %s" % (label, "FINDNEW")
        )
        if result and (response is not None) and (response.status == 207) and (respdata is not None):
            try:
                tree = ElementTree(file=BytesIO(respdata))
            except Exception:
                return hresult

            latest = 0
            request_uri = req.getURI(self.manager.server_info)
            for response in tree.findall("{DAV:}response"):

                # Get href for this response
                href = response.findall("{DAV:}href")
                if len(href) != 1:
                    return False, "           Wrong number of DAV:href elements\n"
                href = href[0].text
                if href != request_uri and (not other or href != skip):

                    # Get all property status
                    propstatus = response.findall("{DAV:}propstat")
                    for props in propstatus:
                        # Determine status for this propstat
                        status = props.findall("{DAV:}status")
                        if len(status) == 1:
                            statustxt = status[0].text
                            status = False
                            if statustxt.startswith("HTTP/1.1 ") and (len(statustxt) >= 10):
                                status = (statustxt[9] == "2")
                        else:
                            status = False

                        if status:
                            # Get properties for this propstat
                            prop = props.findall("{DAV:}prop")
                            for el in prop:

                                # Get properties for this propstat
                                glm = el.findall("{DAV:}getlastmodified")
                                if len(glm) != 1:
                                    continue
                                value = glm[0].text
                                value = parsedate(value)
                                value = time.mktime(value)
                                if value > latest:
                                    possible_matches.clear()
                                    possible_matches.add(href)
                                    latest = value
                                elif value == latest:
                                    possible_matches.add(href)
                        elif not hresult:
                            possible_matches.add(href)

        if len(possible_matches) == 1:
            hresult = possible_matches.pop()
        elif len(possible_matches) > 1:
            not_seen_before = possible_matches - self.previously_found
            if len(not_seen_before) == 1:
                hresult = not_seen_before.pop()
        if hresult:
            self.previously_found.add(hresult)
        return hresult

    def dofindcontains(self, original_request, collection, match, label=""):
        hresult = ""

        uri = collection[0]
        req = request(self.manager)
        req.method = "PROPFIND"
        req.host = original_request.host
        req.port = original_request.port
        req.ruris.append(uri)
        req.ruri = uri
        req.headers["Depth"] = "1"
        if len(collection[1]):
            req.user = collection[1]
        if len(collection[2]):
            req.pswd = collection[2]
        req.data = data(self.manager)
        req.data.value = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
<D:getetag/>
</D:prop>
</D:propfind>
"""
        req.data.content_type = "text/xml"
        result, _ignore_resulttxt, response, respdata = self.dorequest(
            req, False, False, label="%s | %s" % (label, "FINDNEW")
        )
        if result and (response is not None) and (response.status == 207) and (respdata is not None):
            try:
                tree = ElementTree(file=BytesIO(respdata))
            except Exception:
                return hresult

            request_uri = req.getURI(self.manager.server_info)
            for response in tree.findall("{DAV:}response"):

                # Get href for this response
                href = response.findall("{DAV:}href")
                if len(href) != 1:
                    return False, "           Wrong number of DAV:href elements\n"
                href = href[0].text
                if href != request_uri:

                    _ignore_result, respdata = self.doget(req, (
                        href,
                        collection[1],
                        collection[2],
                    ), label)
                    if respdata.find(match) != -1:
                        break
            else:
                href = None

        return href

    def dowaitcount(self, original_request, collection, count, label=""):

        hrefs = []
        for _ignore in range(self.manager.server_info.waitcount):
            req = request(self.manager)
            req.method = "PROPFIND"
            req.host = original_request.host
            req.port = original_request.port
            req.ruris.append(collection[0])
            req.ruri = collection[0]
            req.headers["Depth"] = "1"
            if len(collection[1]):
                req.user = collection[1]
            if len(collection[2]):
                req.pswd = collection[2]
            req.data = data(self.manager)
            req.data.value = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
<D:getetag/>
</D:prop>
</D:propfind>
"""
            req.data.content_type = "text/xml"
            result, _ignore_resulttxt, response, respdata = self.dorequest(
                req, False, False, label="%s | %s %d" % (label, "WAITCOUNT", count)
            )
            hrefs = []
            if result and (response is not None) and (response.status == 207) and (respdata is not None):
                tree = ElementTree(file=BytesIO(respdata))

                for response in tree.findall("{DAV:}response"):
                    href = response.findall("{DAV:}href")[0]
                    if href.text.rstrip("/") != collection[0].rstrip("/"):
                        hrefs.append(href.text)

                if len(hrefs) == count:
                    return True, None
            delay = self.manager.server_info.waitdelay
            starttime = time.time()
            while (time.time() < starttime + delay):
                pass

        if self.manager.debug and hrefs:
            # Get the content of each resource
            rdata = ""
            for href in hrefs:
                result, respdata = self.doget(req, (
                    href,
                    collection[1],
                    collection[2],
                ), label)
                test = "unknown"
                if respdata.startswith("BEGIN:VCALENDAR"):
                    uid = respdata.find("UID:")
                    if uid != -1:
                        uid = respdata[uid + 4:uid + respdata[uid:].find("\r\n")]
                        test = self.uidmaps.get(uid, "unknown")
                rdata += "\n\nhref: {h}\ntest: {t}\n\n{r}\n".format(h=href, t=test, r=respdata)

            return False, rdata
        else:
            return False, len(hrefs)

    def dowaitchanged(self, original_request, uri, etag, user, pswd, label=""):

        for _ignore in range(self.manager.server_info.waitcount):
            req = request(self.manager)
            req.method = "HEAD"
            req.host = original_request.host
            req.port = original_request.port
            req.ruris.append(uri)
            req.ruri = uri
            if user:
                req.user = user
            if pswd:
                req.pswd = pswd
            result, _ignore_resulttxt, response, _ignore_respdata = self.dorequest(
                req, False, False, label="%s | %s" % (label, "WAITCHANGED")
            )
            if result and (response is not None):
                if response.status / 100 == 2:
                    hdrs = response.msg.getheaders("Etag")
                    if hdrs:
                        newetag = hdrs[0].encode("utf-8")
                        if newetag != etag:
                            break
                else:
                    return False
            delay = self.manager.server_info.waitdelay
            starttime = time.time()
            while (time.time() < starttime + delay):
                pass
        else:
            return False

        return True

    def doenddelete(self, description, label=""):
        if len(self.end_deletes) == 0:
            return True
        self.manager.message("trace", "Start: " + description)
        for uri, delete_request in self.end_deletes:
            req = request(self.manager)
            req.method = "DELETE"
            req.host = delete_request.host
            req.port = delete_request.port
            req.ruris.append(uri)
            req.ruri = uri
            req.user = delete_request.user
            req.pswd = delete_request.pswd
            req.cert = delete_request.cert
            self.dorequest(req, False, False, label=label)
        self.manager.message("trace", "{name:<60}{value:>10}".format(name="End: " + description, value="[DONE]"))

    def dorequest(
        self, req, details=False, doverify=True, forceverify=False, stats=None, etags=None, label="", count=1
    ):

        req.count = count

        if isinstance(req, pause):
            # Useful for pausing at a particular point
            print("Paused")
            sys.stdin.readline()
            return True, "", None, None

        if len(req.missingFeatures()) != 0:
            return True, "", None, None
        if len(req.excludedFeatures()) != 0:
            return True, "", None, None

        # Special check for DELETEALL
        if req.method == "DELETEALL":
            for ruri in req.ruris:
                collection = (ruri, req.user, req.pswd)
                hrefs = self.dofindall(req, collection, label="%s | %s" % (label, "DELETEALL"))
                if not self.dodeleteall(req, hrefs, label="%s | %s" % (label, "DELETEALL")):
                    return False, "DELETEALL failed for: {r}".format(r=ruri), None, None
            return True, "", None, None

        # Special for delay
        elif req.method == "DELAY":
            # self.ruri contains a numeric delay in seconds
            delay = int(req.ruri)
            starttime = time.time()
            while (time.time() < starttime + delay):
                pass
            return True, "", None, None

        # Special for GETNEW
        elif req.method == "GETNEW":
            collection = (req.ruri, req.user, req.pswd)
            self.grabbedlocation = self.dofindnew(req, collection, label=label)
            if req.graburi:
                self.manager.server_info.addextrasubs({req.graburi: self.grabbedlocation})
            req.method = "GET"
            req.ruri = "$"

        # Special for FINDNEW
        elif req.method == "FINDNEW":
            collection = (req.ruri, req.user, req.pswd)
            self.grabbedlocation = self.dofindnew(req, collection, label=label)
            if req.graburi:
                self.manager.server_info.addextrasubs({req.graburi: self.grabbedlocation})
            return True, "", None, None

        # Special for GETOTHER
        elif req.method == "GETOTHER":
            collection = (req.ruri, req.user, req.pswd)
            self.grabbedlocation = self.dofindnew(req, collection, label=label, other=True)
            if req.graburi:
                self.manager.server_info.addextrasubs({req.graburi: self.grabbedlocation})
            req.method = "GET"
            req.ruri = "$"

        # Special for GETCONTAINS
        elif req.method.startswith("GETCONTAINS"):
            match = req.method[12:]
            collection = (req.ruri, req.user, req.pswd)
            self.grabbedlocation = self.dofindcontains(req, collection, match, label=label)
            if not self.grabbedlocation:
                return False, "No matching resource", None, None
            if req.graburi:
                self.manager.server_info.addextrasubs({req.graburi: self.grabbedlocation})
            req.method = "GET"
            req.ruri = "$"

        # Special check for WAITCOUNT
        elif req.method.startswith("WAITCOUNT"):
            count = int(req.method[10:])
            for ruri in req.ruris:
                collection = (ruri, req.user, req.pswd)
                waitresult, waitdetails = self.dowaitcount(req, collection, count, label=label)
                if not waitresult:
                    return False, "Count did not change: {w}".format(w=waitdetails), None, None
            else:
                return True, "", None, None

        # Special check for WAITDELETEALL
        elif req.method.startswith("WAITDELETEALL"):
            count = int(req.method[len("WAITDELETEALL"):])
            for ruri in req.ruris:
                collection = (ruri, req.user, req.pswd)
                waitresult, waitdetails = self.dowaitcount(req, collection, count, label=label)
                if waitresult:
                    hrefs = self.dofindall(req, collection, label="%s | %s" % (label, "DELETEALL"))
                    self.dodeleteall(req, hrefs, label="%s | %s" % (label, "DELETEALL"))
                else:
                    return False, "Count did not change: {w}".format(w=waitdetails), None, None
            else:
                return True, "", None, None

        result = True
        resulttxt = ""
        response = None
        respdata = None

        method = req.method
        uri = req.getURI(self.manager.server_info)
        if (uri == "$"):
            uri = self.grabbedlocation
        headers = req.getHeaders(self.manager.server_info)
        data = req.getData()

        # Cache delayed delete
        if req.end_delete:
            self.end_deletes.append((
                uri,
                req,
            ))

        if details:
            resulttxt += "        %s: %s\n" % (method, uri)

        # Special for GETCHANGED
        if req.method == "GETCHANGED":
            if not self.dowaitchanged(req, uri, etags[uri], req.user, req.pswd, label=label):
                return False, "Resource did not change", None, None
            method = "GET"

        # Start request timer if required
        if stats:
            stats.startTimer()

        # Do the http request
        http = SmartHTTPConnection(
            req.host,
            req.port,
            self.manager.server_info.ssl,
            afunix=req.afunix,
            cert=os.path.join(self.manager.server_info.certdir, req.cert) if req.cert else None
        )

        if 'User-Agent' not in headers and label is not None:
            headers['User-Agent'] = label.encode("utf-8")

        try:
            puri = list(urlparse(uri))
            if req.ruri_quote:
                puri[2] = quote(puri[2])
            quri = urlunparse(puri)

            http.request(method, quri, data, headers)

            response = http.getresponse()

            respdata = None
            respdata = response.read()

        finally:
            http.close()

            # Stop request timer before verification
            if stats:
                stats.endTimer()

        if doverify and (respdata is not None):
            result, txt = self.verifyrequest(req, uri, response, respdata)
            resulttxt += txt
        elif forceverify:
            result = (response.status / 100 == 2)
            if not result:
                resulttxt += "Status Code Error: %d" % response.status

        if req.print_request or (
            self.manager.print_request_response_on_error and not result and not req.wait_for_success
        ):
            requesttxt = "\n-------BEGIN:REQUEST-------\n"
            requesttxt += http.requestData
            requesttxt += "\n--------END:REQUEST--------\n"
            self.manager.message("protocol", requesttxt)

        if req.print_response or (
            self.manager.print_request_response_on_error and not result and not req.wait_for_success
        ):
            responsetxt = "\n-------BEGIN:RESPONSE-------\n"
            responsetxt += "%s %s %s\n" % (
                getVersionStringFromResponse(response),
                response.status,
                response.reason,
            )
            responsetxt += str(response.msg) + "\n" + respdata
            responsetxt += "\n--------END:RESPONSE--------\n"
            self.manager.message("protocol", responsetxt)

        if etags is not None and req.method == "GET":
            hdrs = response.msg.getheaders("Etag")
            if hdrs:
                etags[uri] = hdrs[0].encode("utf-8")

        if req.graburi:
            self.manager.server_info.addextrasubs({req.graburi: self.grabbedlocation})

        if req.grabcount:
            ctr = None
            if result and (response is not None) and (response.status == 207) and (respdata is not None):
                tree = ElementTree(file=BytesIO(respdata))
                ctr = len(tree.findall("{DAV:}response")) - 1

            if ctr is None or ctr == -1:
                result = False
                resulttxt += "\nCould not count resources in response\n"
            else:
                self.manager.server_info.addextrasubs({req.grabcount: str(ctr)})

        if req.grabheader:
            for hdrname, variable in req.grabheader:
                hdrs = response.msg.getheaders(hdrname)
                if hdrs:
                    self.manager.server_info.addextrasubs({variable: hdrs[0].encode("utf-8")})
                else:
                    result = False
                    resulttxt += "\nHeader %s was not extracted from response\n" % (hdrname,)

        if req.grabproperty:
            if response.status == 207:
                for propname, variable in req.grabproperty:
                    # grab the property here
                    propvalue = self.extractProperty(propname, respdata)
                    if propvalue is None:
                        result = False
                        resulttxt += "\nProperty %s was not extracted from multistatus response\n" % (propname,)
                    else:
                        self.manager.server_info.addextrasubs({variable: propvalue.encode("utf-8")})

        if req.grabelement:
            for item in req.grabelement:
                if len(item) == 2:
                    elementpath, variables = item
                    parent = None
                else:
                    elementpath, parent, variables = item
                    parent = self.manager.server_info.extrasubs(parent)
                # grab the property here
                elementvalues = self.extractElements(elementpath, parent, respdata)
                if elementvalues is None:
                    result = False
                    resulttxt += "\nElement %s was not extracted from response\n" % (elementpath,)
                elif len(variables) != len(elementvalues):
                    result = False
                    resulttxt += "\n%d found but expecting %d for element %s from response\n" % (
                        len(elementvalues),
                        len(variables),
                        elementpath,
                    )
                else:
                    for variable, elementvalue in zip(variables, elementvalues):
                        self.manager.server_info.addextrasubs({
                            variable: elementvalue.encode("utf-8") if elementvalue else ""
                        })

        if req.grabjson:
            for pointer, variables in req.grabjson:
                # grab the JSON value here
                pointervalues = self.extractPointer(pointer, respdata)
                if pointervalues is None:
                    result = False
                    resulttxt += "\nPointer %s was not extracted from response\n" % (pointer,)
                elif len(variables) != len(pointervalues):
                    result = False
                    resulttxt += "\n%d found but expecting %d for pointer %s from response\n" % (
                        len(pointervalues),
                        len(variables),
                        pointer,
                    )
                else:
                    for variable, pointervalue in zip(variables, pointervalues):
                        self.manager.server_info.addextrasubs({
                            variable: pointervalue.encode("utf-8") if pointervalue else ""
                        })

        if req.grabcalprop:
            for propname, variable in req.grabcalprop:
                # grab the property here
                propname = self.manager.server_info.subs(propname)
                propname = self.manager.server_info.extrasubs(propname)
                propvalue = self.extractCalProperty(propname, respdata)
                if propvalue is None:
                    result = False
                    resulttxt += "\nCalendar property %s was not extracted from response\n" % (propname,)
                else:
                    self.manager.server_info.addextrasubs({variable: propvalue.encode("utf-8")})

        if req.grabcalparam:
            for paramname, variable in req.grabcalparam:
                # grab the property here
                paramname = self.manager.server_info.subs(paramname)
                paramname = self.manager.server_info.extrasubs(paramname)
                paramvalue = self.extractCalParameter(paramname, respdata)
                if paramvalue is None:
                    result = False
                    resulttxt += "\nCalendar Parameter %s was not extracted from response\n" % (paramname,)
                else:
                    self.manager.server_info.addextrasubs({variable: paramvalue.encode("utf-8")})

        return result, resulttxt, response, respdata

    def verifyrequest(self, req, uri, response, respdata):

        result = True
        resulttxt = ""

        # check for response
        if len(req.verifiers) == 0:
            return result, resulttxt
        else:
            result = True
            resulttxt = ""
            for verifier in req.verifiers:
                if len(verifier.missingFeatures()) != 0:
                    continue
                if len(verifier.excludedFeatures()) != 0:
                    continue
                iresult, iresulttxt = verifier.doVerify(uri, response, respdata)
                if not iresult:
                    result = False
                    if len(resulttxt):
                        resulttxt += "\n"
                    resulttxt += "Failed Verifier: %s\n" % verifier.callback
                    resulttxt += iresulttxt
                else:
                    if len(resulttxt):
                        resulttxt += "\n"
                    resulttxt += "Passed Verifier: %s\n" % verifier.callback

            if result:
                resulttxt = ""
            return result, resulttxt

    def parseXML(self, node):
        self.ignore_all = node.get(src.xmlDefs.ATTR_IGNORE_ALL, src.xmlDefs.ATTR_VALUE_NO) == src.xmlDefs.ATTR_VALUE_YES

        for child in node:
            if child.tag == src.xmlDefs.ELEMENT_DESCRIPTION:
                self.description = child.text
            elif child.tag == src.xmlDefs.ELEMENT_REQUIRE_FEATURE:
                self.parseFeatures(child, require=True)
            elif child.tag == src.xmlDefs.ELEMENT_EXCLUDE_FEATURE:
                self.parseFeatures(child, require=False)
            elif child.tag == src.xmlDefs.ELEMENT_START:
                self.start_requests = request.parseList(self.manager, child)
            elif child.tag == src.xmlDefs.ELEMENT_TESTSUITE:
                suite = testsuite(self.manager)
                suite.parseXML(child)
                self.suites.append(suite)
            elif child.tag == src.xmlDefs.ELEMENT_END:
                self.end_requests = request.parseList(self.manager, child)

    def parseFeatures(self, node, require=True):
        for child in node:
            if child.tag == src.xmlDefs.ELEMENT_FEATURE:
                (self.require_features if require else self.exclude_features).add(child.text)

    def extractProperty(self, propertyname, respdata):

        try:
            tree = ElementTree(file=BytesIO(respdata))
        except Exception:
            return None

        for response in tree.findall("{DAV:}response"):
            # Get all property status
            propstatus = response.findall("{DAV:}propstat")
            for props in propstatus:
                # Determine status for this propstat
                status = props.findall("{DAV:}status")
                if len(status) == 1:
                    statustxt = status[0].text
                    status = False
                    if statustxt.startswith("HTTP/1.1 ") and (len(statustxt) >= 10):
                        status = (statustxt[9] == "2")
                else:
                    status = False

                if not status:
                    continue

                # Get properties for this propstat
                prop = props.findall("{DAV:}prop")
                if len(prop) != 1:
                    return False, "           Wrong number of DAV:prop elements\n"

                for child in prop[0].getchildren():
                    fqname = child.tag
                    if len(child):
                        # Copy sub-element data as text into one long string and strip leading/trailing space
                        value = ""
                        for p in child.getchildren():
                            temp = tostring(p)
                            temp = temp.strip()
                            value += temp
                    else:
                        value = child.text

                    if fqname == propertyname:
                        return value

        return None

    def extractElement(self, elementpath, respdata):

        try:
            tree = ElementTree()
            tree.parse(BytesIO(respdata))
        except:  # noqa
            return None

        # Strip off the top-level item
        if elementpath[0] == '/':
            elementpath = elementpath[1:]
            splits = elementpath.split('/', 1)
            root = splits[0]
            if tree.getroot().tag != root:
                return None
            elif len(splits) == 1:
                return tree.getroot().text
            else:
                elementpath = splits[1]

        e = tree.find(elementpath)
        if e is not None:
            return e.text
        else:
            return None

    def extractElements(self, elementpath, parent, respdata):

        try:
            tree = ElementTree()
            tree.parse(BytesIO(respdata))
        except:  # noqa
            return None

        if parent:
            tree_root = nodeForPath(tree.getroot(), parent)
            if not tree_root:
                return None
            tree_root = tree_root[0]

            # Handle absolute root element
            if elementpath[0] == '/':
                elementpath = elementpath[1:]
            root_path, child_path = xmlPathSplit(elementpath)
            if child_path:
                if tree_root.tag != root_path:
                    return None
                e = tree_root.findall(child_path)
            else:
                e = (tree_root,)

        else:
            # Strip off the top-level item
            if elementpath[0] == '/':
                elementpath = elementpath[1:]
                splits = elementpath.split('/', 1)
                root = splits[0]
                if tree.getroot().tag != root:
                    return None
                elif len(splits) == 1:
                    return tree.getroot().text
                else:
                    elementpath = splits[1]

            e = tree.findall(elementpath)

        if e is not None:
            return [item.text for item in e]
        else:
            return None

    def extractPointer(self, pointer, respdata):

        jp = JSONMatcher(pointer)

        try:
            j = json.loads(respdata)
        except:  # noqa
            return None

        return jp.match(j)

    def extractCalProperty(self, propertyname, respdata):

        prop = self._calProperty(propertyname, respdata)
        return prop.getValue().getValue() if prop else None

    def extractCalParameter(self, parametername, respdata):

        # propname is a path consisting of component names and the last one a property name
        # e.g. VEVENT/ATTACH
        bits = parametername.split("/")
        propertyname = "/".join(bits[:-1])
        param = bits[-1]
        bits = param.split("$")
        pname = bits[0]
        if len(bits) > 1:
            propertyname += "$%s" % (bits[1],)

        prop = self._calProperty(propertyname, respdata)

        try:
            return prop.getParameterValue(pname) if prop else None
        except KeyError:
            return None

    def _calProperty(self, propertyname, respdata):

        try:
            cal = Calendar.parseText(respdata)
        except Exception:
            return None

        # propname is a path consisting of component names and the last one a property name
        # e.g. VEVENT/ATTACH
        bits = propertyname.split("/")
        components = bits[:-1]
        prop = bits[-1]
        bits = prop.split("$")
        pname = bits[0]
        pvalue = bits[1] if len(bits) > 1 else None

        while components:
            for c in cal.getComponents():
                if c.getType() == components[0]:
                    cal = c
                    components = components[1:]
                    break
            else:
                break

        if components:
            return None

        props = cal.getProperties(pname)
        if pvalue:
            for prop in props:
                if prop.getValue().getValue() == pvalue:
                    return prop
            else:
                return None
        else:
            return props[0] if props else None

    def postgresInit(self):
        """
        Initialize postgres statement counter
        """
        if self.manager.postgresLog:
            if os.path.exists(self.manager.postgresLog):
                return int(subprocess.getoutput("grep \"LOG:  statement:\" %s | wc -l" % (self.manager.postgresLog,)))

        return 0

    def postgresResult(self, startCount, indent):

        if self.manager.postgresLog:
            if os.path.exists(self.manager.postgresLog):
                newCount = int(
                    subprocess.getoutput("grep \"LOG:  statement:\" %s | wc -l" % (self.manager.postgresLog,))
                )
            else:
                newCount = 0
            self.manager.message("trace", "Postgres Statements: %d" % (newCount - startCount,))
