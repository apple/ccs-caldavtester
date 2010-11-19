##
# Copyright (c) 2006-2010 Apple Inc. All rights reserved.
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

from cStringIO import StringIO
from src.httpshandler import SmartHTTPConnection
from src.manager import manager
from src.request import data, pause
from src.request import request
from src.request import stats
from src.testsuite import testsuite
from xml.etree.ElementTree import ElementTree, tostring
import commands
import os
import rfc822
import socket
import src.xmlDefs
import sys
import time

STATUSTXT_WIDTH    = 60

class caldavtest(object):
    
    def __init__( self, manager, name ):
        self.manager = manager
        self.name = name
        self.description = ""
        self.require_features = set()
        self.ignore_all = False
        self.start_requests = []
        self.end_requests = []
        self.end_deletes = []
        self.suites = []
        self.grabbedlocation = None
        
    def missingFeatures(self):
        return self.require_features - self.manager.server_info.features

    def run( self ):
        if len(self.missingFeatures()) != 0:
            self.manager.log(manager.LOG_HIGH, "----- Ignoring Tests from \"%s\"... -----" % self.name, before=1)
            self.manager.log(manager.LOG_HIGH, "      Missing features: %s" % (", ".join(sorted(self.missingFeatures())),))
            return 0, 0, 1
            
        try:
            self.manager.log(manager.LOG_HIGH, "----- Running Tests from \"%s\"... -----" % self.name, before=1)
            result = self.dorequests( "Executing Start Requests...", self.start_requests, False, True, label="%s | %s" % (self.name, "START_REQUESTS") )
            if not result:
                self.manager.log(manager.LOG_ERROR, "Start items failed - tests will not be run.")
                ok = 0
                failed = 1
                ignored = 0
            else:
                ok, failed, ignored = self.run_tests(label=self.name)
            self.doenddelete( "Deleting Requests...", label="%s | %s" % (self.name, "END_DELETE"))
            self.dorequests( "Executing End Requests...", self.end_requests, False, label="%s | %s" % (self.name, "END_REQUESTS"))
            return ok, failed, ignored
        except socket.error, msg:
            self.manager.log(manager.LOG_ERROR, "SOCKET ERROR: %s" % (msg,), before=2)
            return 0, 1, 0
        except Exception, e:
            self.manager.log(manager.LOG_ERROR, "FATAL ERROR: %s" % (e,), before=2)
            return 0, 1, 0
        
    def run_tests( self, label = "" ):
        ok = 0
        failed = 0
        ignored = 0
        for suite in self.suites:
            o, f, i = self.run_test_suite( suite, label="%s | %s" % (label, suite.name) )
            ok += o
            failed += f
            ignored += i
        return (ok, failed, ignored)
    
    def run_test_suite( self, suite, label = "" ):
        descriptor = "    Test Suite: %s" % suite.name
        descriptor += " " * max(1, STATUSTXT_WIDTH - len(descriptor))
        self.manager.log(manager.LOG_HIGH, "%s" % (descriptor,), before=1, after=0)
        ok = 0
        failed = 0
        ignored = 0
        postgresCount = None
        if suite.ignore:
            self.manager.log(manager.LOG_HIGH, "[IGNORED]")
            ignored = len(suite.tests)
        elif len(suite.missingFeatures()) != 0:
            self.manager.log(manager.LOG_HIGH, "[IGNORED]")
            self.manager.log(manager.LOG_HIGH, "      Missing features: %s" % (", ".join(sorted(suite.missingFeatures())),))
            ignored = len(suite.tests)
        else:
            self.manager.log(manager.LOG_HIGH, "")
            postgresCount = self.postgresInit()
            if self.manager.memUsage:
                start_usage = self.manager.getMemusage()
            etags = {}
            for test in suite.tests:
                result = self.run_test( test, etags, label="%s | %s" % (label, test.name) )
                if result == "t":
                    ok += 1
                elif result == "f":
                    failed += 1
                else:
                    ignored += 1
            if self.manager.memUsage:
                end_usage = self.manager.getMemusage()
                print start_usage, end_usage
                self.manager.log(manager.LOG_HIGH, "Mem. Usage: RSS=%s%% VSZ=%s%%" % (str(((end_usage[1] - start_usage[1]) * 100)/start_usage[1]), str(((end_usage[0] - start_usage[0]) * 100)/start_usage[0]))) 
        self.manager.log(manager.LOG_HIGH, "Suite Results: %d PASSED, %d FAILED, %d IGNORED" % (ok, failed, ignored), before=1, indent=4)
        if postgresCount is not None:
            self.postgresResult(postgresCount, indent=4)
        return (ok, failed, ignored)
            
    def run_test( self, test, etags, label = "" ):
        descriptor = "        Test: %s" % test.name
        descriptor += " " * max(1, STATUSTXT_WIDTH - len(descriptor))
        self.manager.log(manager.LOG_HIGH, "%s" % (descriptor,), before=1, after=0)
        if test.ignore:
            self.manager.log(manager.LOG_HIGH, "[IGNORED]")
            return "i"
        elif len(test.missingFeatures()) != 0:
            self.manager.log(manager.LOG_HIGH, "[IGNORED]")
            self.manager.log(manager.LOG_HIGH, "      Missing features: %s" % (", ".join(sorted(test.missingFeatures())),))
            return "i"
        else:
            result = False
            resulttxt = ""
            postgresCount = self.postgresInit()
            if test.stats:
                reqstats = stats()
            else:
                reqstats = None
            for ctr in range(test.count): #@UnusedVariable
                for req in test.requests:
                    result, resulttxt, _ignore_response, _ignore_respdata = self.dorequest( req, test.details, True, False, reqstats, etags = etags, label=label, count=ctr+1 )
                    if not result:
                        break
            loglevel = [manager.LOG_ERROR, manager.LOG_HIGH][result]
            self.manager.log(loglevel, ["[FAILED]", "[OK]"][result])
            if len(resulttxt) > 0:
                self.manager.log(loglevel, resulttxt)
            if result and test.stats:
                self.manager.log(manager.LOG_MEDIUM, "Total Time: %.3f secs" % (reqstats.totaltime,), indent=8)
                self.manager.log(manager.LOG_MEDIUM, "Average Time: %.3f secs" % (reqstats.totaltime/reqstats.count,), indent=8)
            self.postgresResult(postgresCount, indent=8)
            return ["f", "t"][result]
    
    def dorequests( self, description, list, doverify = True, forceverify = False, label = "", count = 1 ):
        if len(list) == 0:
            return True
        description += " " * max(1, STATUSTXT_WIDTH - len(description))
        self.manager.log(manager.LOG_HIGH, description, before=1, after=0)
        ctr = 1
        for req in list:
            result, resulttxt, _ignore_response, _ignore_respdata = self.dorequest( req, False, doverify, forceverify, label=label, count=count )
            if not result:
                resulttxt += "\nFailure during multiple requests #%d out of %d, request=%s" % (ctr, len(list), str(req))
                break
            ctr += 1
        loglevel = [manager.LOG_ERROR, manager.LOG_HIGH][result]
        self.manager.log(loglevel, ["[FAILED]", "[OK]"][result])
        if len(resulttxt) > 0:
            self.manager.log(loglevel, resulttxt)
        return result
    
    def dofindall( self, collection, label = "" ):
        hrefs = []
        req = request(self.manager)
        req.method = "PROPFIND"
        req.ruris.append(collection[0])
        req.ruri = collection[0]
        req.headers["Depth"] = "1"
        if len(collection[1]):
            req.user = collection[1]
        if len(collection[2]):
            req.pswd = collection[2]
        req.data = data()
        req.data.value = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
<D:getetag/>
</D:prop>
</D:propfind>
"""
        req.data.content_type = "text/xml"
        result, _ignore_resulttxt, response, respdata = self.dorequest( req, False, False, label=label )
        if result and (response is not None) and (response.status == 207) and (respdata is not None):
            try:
                tree = ElementTree(file=StringIO(respdata))
            except Exception:
                return ()

            request_uri = req.getURI( self.manager.server_info )
            for response in tree.findall("{DAV:}response"):
    
                # Get href for this response
                href = response.findall("{DAV:}href")
                if len(href) != 1:
                    return False, "           Wrong number of DAV:href elements\n"
                href = href[0].text
                if href != request_uri:
                    hrefs.append((href, collection[1], collection[2]) )
        return hrefs

    def dodeleteall( self, deletes, label = "" ):
        if len(deletes) == 0:
            return True
        for deleter in deletes:
            req = request(self.manager)
            req.method = "DELETE"
            req.ruris.append(deleter[0])
            req.ruri = deleter[0]
            if len(deleter[1]):
                req.user = deleter[1]
            if len(deleter[2]):
                req.pswd = deleter[2]
            self.dorequest( req, False, False, label=label )

    def dofindnew( self, collection, label = "" ):
        hresult = ""
        req = request(self.manager)
        req.method = "PROPFIND"
        req.ruris.append(collection[0])
        req.ruri = collection[0]
        req.headers["Depth"] = "1"
        if len(collection[1]):
            req.user = collection[1]
        if len(collection[2]):
            req.pswd = collection[2]
        req.data = data()
        req.data.value = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
<D:getetag/>
<D:getlastmodified/>
</D:prop>
</D:propfind>
"""
        req.data.content_type = "text/xml"
        result, _ignore_resulttxt, response, respdata = self.dorequest( req, False, False, label="%s | %s" % (label, "FINDNEW") )
        if result and (response is not None) and (response.status == 207) and (respdata is not None):
            try:
                tree = ElementTree(file=StringIO(respdata))
            except Exception:
                return hresult

            latest = 0
            request_uri = req.getURI( self.manager.server_info )
            for response in tree.findall("{DAV:}response" ):
    
                # Get href for this response
                href = response.findall("{DAV:}href")
                if len(href) != 1:
                    return False, "           Wrong number of DAV:href elements\n"
                href = href[0].text
                if href != request_uri:

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
                        
                        # Get properties for this propstat
                        prop = props.findall("{DAV:}prop")
                        for el in prop:

                            # Get properties for this propstat
                            glm = el.findall("{DAV:}getlastmodified")
                            if len(glm) != 1:
                                continue
                            value = glm[0].text
                            value = rfc822.parsedate(value)
                            value = time.mktime(value)
                            if value > latest:
                                hresult = href
                                latest = value

        return hresult

    def dowaitcount( self, collection, count, label = ""):
        
        for _ignore in range(30):
            req = request(self.manager)
            req.method = "PROPFIND"
            req.ruris.append(collection[0])
            req.ruri = collection[0]
            req.headers["Depth"] = "1"
            if len(collection[1]):
                req.user = collection[1]
            if len(collection[2]):
                req.pswd = collection[2]
            req.data = data()
            req.data.value = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
<D:getetag/>
</D:prop>
</D:propfind>
"""
            req.data.content_type = "text/xml"
            result, _ignore_resulttxt, response, respdata = self.dorequest( req, False, False, label="%s | %s %d" % (label, "WAITCOUNT", count) )
            ctr = 0
            if result and (response is not None) and (response.status == 207) and (respdata is not None):
                tree = ElementTree(file=StringIO(respdata))

                for response in tree.findall("{DAV:}response"):
                    ctr += 1
                
                if ctr - 1 == count:
                    return True
            delay = 1
            starttime = time.time()
            while (time.time() < starttime + delay):
                pass
        else:
            return False

    def dowaitchanged( self, uri, etag, user, pswd, label = "" ):
        
        for _ignore in range(30):
            req = request(self.manager)
            req.method = "HEAD"
            req.ruris.append(uri)
            req.ruri = uri
            if user:
                req.user = user
            if pswd:
                req.pswd = pswd
            result, _ignore_resulttxt, response,  _ignore_respdata = self.dorequest( req, False, False, label="%s | %s" % (label, "WAITCHANGED") )
            if result and (response is not None):
                if response.status / 100 == 2:
                    hdrs = response.msg.getheaders("Etag")
                    if hdrs:
                        newetag = hdrs[0].encode("utf-8")
                        if newetag != etag:
                            break
                else:
                    return False
            delay = 1
            starttime = time.time()
            while (time.time() < starttime + delay):
                pass
        else:
            return False

        return True

    def doenddelete( self, description, label = "" ):
        if len(self.end_deletes) == 0:
            return True
        description += " " * max(1, STATUSTXT_WIDTH - len(description))
        self.manager.log(manager.LOG_HIGH, description, before=1, after=0)
        for deleter in self.end_deletes:
            req = request(self.manager)
            req.method = "DELETE"
            req.ruris.append(deleter[0])
            req.ruri = deleter[0]
            if len(deleter[1]):
                req.user = deleter[1]
            if len(deleter[2]):
                req.pswd = deleter[2]
            self.dorequest( req, False, False, label=label )
        self.manager.log(manager.LOG_HIGH, "[DONE]")
    
    def dorequest( self, req, details=False, doverify = True, forceverify = False, stats = None, etags = None, label = "", count = 1 ):
        
        req.count = count

        if isinstance(req, pause):
            # Useful for pausing at a particular point
            print "Paused"
            sys.stdin.readline()
            return True, "", None, None
            
        if len(req.missingFeatures()) != 0:
            #self.manager.log(manager.LOG_HIGH, "[IGNORED]")
            #self.manager.log(manager.LOG_HIGH, "      Missing features: %s" % (", ".join(sorted(req.missingFeatures())),))
            return True, "", None, None

        # Special check for DELETEALL
        if req.method == "DELETEALL":
            for ruri in req.ruris:
                collection = (ruri, req.user, req.pswd)
                hrefs = self.dofindall(collection, label="%s | %s" % (label, "DELETEALL"))
                self.dodeleteall(hrefs, label="%s | %s" % (label, "DELETEALL"))
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
            self.grabbedlocation = self.dofindnew(collection, label=label)
            req.method = "GET"
            req.ruri = "$"
            
        # Special check for WAITCOUNT
        elif req.method.startswith("WAITCOUNT"):
            count = int(req.method[10:])
            collection = (req.ruri, req.user, req.pswd)
            if self.dowaitcount(collection, count, label=label):
                return True, "", None, None
            else:
                return False, "Count did not change", None, None

        elif req.method == "BREAK":
            # Useful for setting a break point
            return True, "", None, None

        elif req.method == "PAUSE":
            # Useful for pausing at a particular point
            print "Paused"
            sys.stdin.readline()
            return True, "", None, None

        result = True;
        resulttxt = ""
        response = None
        respdata = None

        method = req.method
        uri = req.getURI( self.manager.server_info )
        if (uri == "$"):
            uri = self.grabbedlocation
        headers = req.getHeaders( self.manager.server_info )
        data = req.getData()
        
        # Cache delayed delete
        if req.end_delete:
            self.end_deletes.append( (uri, req.user, req.pswd) )

        if details:
            resulttxt += "        %s: %s\n" % ( method, uri )

        # Special for GETCHANGED
        if req.method == "GETCHANGED":
            if not self.dowaitchanged(uri, etags[uri], req.user, req.pswd,
                label=label):
                return False, "Resource did not change", None, None
            method = "GET"

        # Start request timer if required
        if stats:
            stats.startTimer()

        # Do the http request
        http = SmartHTTPConnection( self.manager.server_info.host, self.manager.server_info.port, self.manager.server_info.ssl )

        if not headers.has_key('User-Agent') and label is not None:
            headers['User-Agent'] = label.encode("utf-8")

        try:
            #self.manager.log(manager.LOG_LOW, "Sending request")
            http.request( method, uri, data, headers )
            #self.manager.log(manager.LOG_LOW, "Sent request")
        
            response = http.getresponse()
        
            respdata = None
            respdata = response.read()
            #self.manager.log(manager.LOG_LOW, "Read response")

        finally:
            http.close()
        
            # Stop request timer before verification
            if stats:
                stats.endTimer()

        if doverify and (respdata != None):
            result, txt = self.verifyrequest( req, uri, response, respdata )
            resulttxt += txt
        elif forceverify:
            result = (response.status / 100 == 2)
            if not result:
                resulttxt += "Status Code Error: %d" % response.status
        
        if req.print_response:
            resulttxt += "\n-------BEGIN:RESPONSE-------\n"
            resulttxt += "Status = %d\n" % response.status
            resulttxt += str(response.msg) + "\n" + respdata
            resulttxt += "\n--------END:RESPONSE--------\n"
        
        if etags is not None and req.method == "GET":
            hdrs = response.msg.getheaders("Etag")
            if hdrs:
                etags[uri] = hdrs[0].encode("utf-8")

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
                    if propvalue == None:
                        result = False
                        resulttxt += "\nProperty %s was not extracted from multistatus response\n" % (propname,)
                    else:
                        self.manager.server_info.addextrasubs({variable: propvalue.encode("utf-8")})

        if req.grabelement:
            for elementpath, variable in req.grabelement:
                # grab the property here
                elementvalue = self.extractElement(elementpath, respdata)
                if elementvalue == None:
                    result = False
                    resulttxt += "\Element %s was not extracted from response\n" % (elementpath,)
                else:
                    self.manager.server_info.addextrasubs({variable: elementvalue.encode("utf-8")})

        return result, resulttxt, response, respdata

    def verifyrequest( self, req, uri, response, respdata ):
        
        result = True;
        resulttxt = ""
        
        # check for response
        if len(req.verifiers) == 0:
            return result, resulttxt
        else:
            result = True
            resulttxt = ""
            for verifier in req.verifiers:
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

    def parseXML( self, node ):
        self.ignore_all = node.get(src.xmlDefs.ATTR_IGNORE_ALL, src.xmlDefs.ATTR_VALUE_NO) == src.xmlDefs.ATTR_VALUE_YES

        for child in node.getchildren():
            if child.tag == src.xmlDefs.ELEMENT_DESCRIPTION:
                self.description = child.text
            elif child.tag == src.xmlDefs.ELEMENT_REQUIRE_FEATURE:
                self.parseFeatures(child)
            elif child.tag == src.xmlDefs.ELEMENT_START:
                self.start_requests = request.parseList(self.manager, child)
            elif child.tag == src.xmlDefs.ELEMENT_TESTSUITE:
                suite = testsuite(self.manager)
                suite.parseXML(child)
                self.suites.append(suite)
            elif child.tag == src.xmlDefs.ELEMENT_END:
                self.end_requests = request.parseList(self.manager, child)
    
    def parseFeatures(self, node):
        for child in node.getchildren():
            if child.tag == src.xmlDefs.ELEMENT_FEATURE:
                self.require_features.add(child.text.encode("utf-8"))

    def extractProperty(self, propertyname, respdata):

        try:
            tree = ElementTree(file=StringIO(respdata))
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
                        value = ""
                    
                    if fqname == propertyname:
                        return value

        return None
    

    def extractElement(self, elementpath, respdata):

        try:
            tree = ElementTree()
            tree.parse(StringIO(respdata))
        except:
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

    def postgresInit(self):
        """
        Initialize postgres statement counter
        """
        if self.manager.postgresLog:
            if os.path.exists(self.manager.postgresLog):
                return int(commands.getoutput("grep \"LOG:  statement:\" %s | wc -l" % (self.manager.postgresLog,)))

        return 0
        
    def postgresResult(self, startCount, indent):
        
        if self.manager.postgresLog:
            if os.path.exists(self.manager.postgresLog):
                newCount = int(commands.getoutput("grep \"LOG:  statement:\" %s | wc -l" % (self.manager.postgresLog,)))
            else:
                newCount = 0
            self.manager.log(manager.LOG_HIGH, "Postgres Statements: %d" % (newCount - startCount,), indent=indent)
