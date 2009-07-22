##
# Copyright (c) 2006-2009 Apple Inc. All rights reserved.
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

from src.manager import manager
from src.request import data
from src.request import request
from src.request import stats
from src.testsuite import testsuite
from utilities.xmlutils import ElementsByName

from xml.dom.minicompat import NodeList
from xml.dom.minidom import Element
from xml.dom.minidom import Node

import httplib
import rfc822
import socket
import src.xmlDefs
import time
import xml.dom.minidom

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
            self.manager.log(manager.LOG_HIGH, "----- Ignoring CalDAV Tests from \"%s\"... -----" % self.name, before=1)
            self.manager.log(manager.LOG_HIGH, "      Missing features: %s" % (", ".join(sorted(self.missingFeatures())),))
            return 0, 0, 1
            
        try:
            self.manager.log(manager.LOG_HIGH, "----- Running CalDAV Tests from \"%s\"... -----" % self.name, before=1)
            result = self.dorequests( "Executing Start Requests...", self.start_requests, False, True )
            if not result:
                self.manager.log(manager.LOG_ERROR, "Start items failed - tests will not be run.")
                ok = 0
                failed = 1
                ignored = 0
            else:
                ok, failed, ignored = self.run_tests()
            self.doenddelete( "Deleting Requests..." )
            self.dorequests( "Executing End Requests...", self.end_requests, False )
            return ok, failed, ignored
        except socket.error, msg:
            self.manager.log(manager.LOG_ERROR, "SOCKET ERROR: %s" % (msg,), before=2)
            return 0, 1, 0
        except Exception, e:
            self.manager.log(manager.LOG_ERROR, "FATAL ERROR: %s" % (e,), before=2)
            return 0, 1, 0
        
    def run_tests( self ):
        ok = 0
        failed = 0
        ignored = 0
        for suite in self.suites:
            o, f, i = self.run_test_suite( suite )
            ok += o
            failed += f
            ignored += i
        return (ok, failed, ignored)
    
    def run_test_suite( self, suite ):
        descriptor = "    Test Suite: %s" % suite.name
        descriptor += " " * max(1, STATUSTXT_WIDTH - len(descriptor))
        self.manager.log(manager.LOG_HIGH, "%s" % (descriptor,), before=1, after=0)
        ok = 0
        failed = 0
        ignored = 0
        if suite.ignore:
            self.manager.log(manager.LOG_HIGH, "[IGNORED]")
            ignored = len(suite.tests)
        elif len(suite.missingFeatures()) != 0:
            self.manager.log(manager.LOG_HIGH, "[IGNORED]")
            self.manager.log(manager.LOG_HIGH, "      Missing features: %s" % (", ".join(sorted(self.missingFeatures())),))
            ignored = len(suite.tests)
        else:
            self.manager.log(manager.LOG_HIGH, "")
            if self.manager.memUsage:
                start_usage = self.manager.getMemusage()
            for test in suite.tests:
                result = self.run_test( test )
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
        return (ok, failed, ignored)
            
    def run_test( self, test ):
        descriptor = "        Test: %s" % test.name
        descriptor += " " * max(1, STATUSTXT_WIDTH - len(descriptor))
        self.manager.log(manager.LOG_HIGH, "%s" % (descriptor,), before=1, after=0)
        if test.ignore:
            self.manager.log(manager.LOG_HIGH, "[IGNORED]")
            return "i"
        else:
            result = False
            resulttxt = ""
            if test.stats:
                reqstats = stats()
            else:
                reqstats = None
            for ctr in range(test.count): #@UnusedVariable
                for req in test.requests:
                    result, resulttxt, _ignore_response, _ignore_respdata = self.dorequest( req, test.details, True, False, reqstats )
                    if not result:
                        break
            loglevel = [manager.LOG_ERROR, manager.LOG_HIGH][result]
            self.manager.log(loglevel, ["[FAILED]", "[OK]"][result])
            if len(resulttxt) > 0:
                self.manager.log(loglevel, resulttxt)
            if result and test.stats:
                self.manager.log(manager.LOG_MEDIUM, "Total Time: %.3f secs" % (reqstats.totaltime,), indent=8)
                self.manager.log(manager.LOG_MEDIUM, "Average Time: %.3f secs" % (reqstats.totaltime/reqstats.count,), indent=8)
            return ["f", "t"][result]
    
    def dorequests( self, description, list, doverify = True, forceverify = False ):
        if len(list) == 0:
            return True
        description += " " * max(1, STATUSTXT_WIDTH - len(description))
        self.manager.log(manager.LOG_HIGH, description, before=1, after=0)
        ctr = 1
        for req in list:
            result, resulttxt, _ignore_response, _ignore_respdata = self.dorequest( req, False, doverify, forceverify )
            if not result:
                resulttxt += "\nFailure during multiple requests #%d out of %d, request=%s" % (ctr, len(list), str(req))
                break
            ctr += 1
        loglevel = [manager.LOG_ERROR, manager.LOG_HIGH][result]
        self.manager.log(loglevel, ["[FAILED]", "[OK]"][result])
        if len(resulttxt) > 0:
            self.manager.log(loglevel, resulttxt)
        return result
    
    def dofindall( self, collection):
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
        result, _ignore_resulttxt, response, respdata = self.dorequest( req, False, False )
        if result and (response is not None) and (response.status == 207) and (respdata is not None):
            doc = xml.dom.minidom.parseString( respdata )

            def ElementsByName(parent, nsURI, localName):
                rc = NodeList()
                for node in parent.childNodes:
                    if node.nodeType == Node.ELEMENT_NODE:
                        if ((localName == "*" or node.localName == localName) and
                            (nsURI == "*" or node.namespaceURI == nsURI)):
                            rc.append(node)
                return rc

            for response in doc.getElementsByTagNameNS( "DAV:", "response" ):
    
                # Get href for this response
                href = ElementsByName(response, "DAV:", "href")
                if len(href) != 1:
                    return False, "           Wrong number of DAV:href elements\n"
                if href[0].firstChild is not None:
                    href = href[0].firstChild.data
                    if href != req.ruri:
                        hrefs.append((href, collection[1], collection[2]) )
        return hrefs

    def dodeleteall( self, deletes ):
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
            self.dorequest( req, False, False )

    def dofindnew( self, collection):
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
        result, _ignore_resulttxt, response, respdata = self.dorequest( req, False, False )
        if result and (response is not None) and (response.status == 207) and (respdata is not None):
            doc = xml.dom.minidom.parseString( respdata )

            def ElementsByName(parent, nsURI, localName):
                rc = NodeList()
                for node in parent.childNodes:
                    if node.nodeType == Node.ELEMENT_NODE:
                        if ((localName == "*" or node.localName == localName) and
                            (nsURI == "*" or node.namespaceURI == nsURI)):
                            rc.append(node)
                return rc

            latest = 0
            for response in doc.getElementsByTagNameNS( "DAV:", "response" ):
    
                # Get href for this response
                href = ElementsByName(response, "DAV:", "href")
                if len(href) != 1:
                    return False, "           Wrong number of DAV:href elements\n"
                if href[0].firstChild is not None:
                    href = href[0].firstChild.data
                    if href != req.ruri:

                        # Get all property status
                        propstatus = ElementsByName(response, "DAV:", "propstat")
                        for props in propstatus:
                            # Determine status for this propstat
                            status = ElementsByName(props, "DAV:", "status")
                            if len(status) == 1:
                                statustxt = status[0].firstChild.data
                                status = False
                                if statustxt.startswith("HTTP/1.1 ") and (len(statustxt) >= 10):
                                    status = (statustxt[9] == "2")
                            else:
                                status = False
                            
                            # Get properties for this propstat
                            prop = ElementsByName(props, "DAV:", "prop")
                            for el in prop:
    
                                # Get properties for this propstat
                                glm = ElementsByName(el, "DAV:", "getlastmodified")
                                if len(glm) != 1:
                                    continue
                                if glm[0].firstChild is not None:
                                    value = glm[0].firstChild.data
                                    value = rfc822.parsedate(value)
                                    value = time.mktime(value)
                                    if value > latest:
                                        hresult = href
                                        latest = value

        return hresult

    def doenddelete( self, description ):
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
            self.dorequest( req, False, False )
        self.manager.log(manager.LOG_HIGH, "[DONE]")
    
    def dorequest( self, req, details=False, doverify = True, forceverify = False, stats = None ):
        
        # Special check for DELETEALL
        if req.method == "DELETEALL":
            for ruri in req.ruris:
                collection = (ruri, req.user, req.pswd)
                hrefs = self.dofindall(collection)
                self.dodeleteall(hrefs)
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
            self.grabbedlocation = self.dofindnew(collection)
            req.method = "GET"
            req.ruri = "$"
            
        result = True;
        resulttxt = ""
        response = None
        respdata = None

        # Cache delayed delete
        if req.end_delete:
            self.end_deletes.append( (req.ruri, req.user, req.pswd) )

        method = req.method
        uri = req.getURI( self.manager.server_info )
        if (uri == "$"):
            uri = self.grabbedlocation
        headers = req.getHeaders( self.manager.server_info )
        data = req.getData()
        
        if details:
            resulttxt += "        %s: %s\n" % ( method, uri )

        # Start request timer if required
        if stats:
            stats.startTimer()

        # Do the http request
        if self.manager.server_info.ssl:
            http = httplib.HTTPSConnection( self.manager.server_info.host, self.manager.server_info.port )
        else:
            http = httplib.HTTPConnection( self.manager.server_info.host, self.manager.server_info.port )
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
        self.ignore_all = node.getAttribute( src.xmlDefs.ATTR_IGNORE_ALL ) == src.xmlDefs.ATTR_VALUE_YES

        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_DESCRIPTION:
                self.description = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_REQUIRE_FEATURE:
                self.parseFeatures( child )
            elif child._get_localName() == src.xmlDefs.ELEMENT_START:
                self.start_requests = request.parseList( self.manager, child )
            elif child._get_localName() == src.xmlDefs.ELEMENT_TESTSUITE:
                suite = testsuite(self.manager)
                suite.parseXML( child )
                self.suites.append( suite )
            elif child._get_localName() == src.xmlDefs.ELEMENT_END:
                self.end_requests = request.parseList( self.manager, child )
    
    def parseFeatures(self, node):
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_FEATURE:
                self.require_features.add(child.firstChild.data.encode("utf-8"))

    def extractProperty(self, propertyname, respdata):

        try:
            doc = xml.dom.minidom.parseString( respdata )
        except:
            return None
                
        for response in doc.getElementsByTagNameNS( "DAV:", "response" ):
            # Get all property status
            propstatus = ElementsByName(response, "DAV:", "propstat")
            for props in propstatus:
                # Determine status for this propstat
                status = ElementsByName(props, "DAV:", "status")
                if len(status) == 1:
                    statustxt = status[0].firstChild.data
                    status = False
                    if statustxt.startswith("HTTP/1.1 ") and (len(statustxt) >= 10):
                        status = (statustxt[9] == "2")
                else:
                    status = False
                
                if not status:
                    continue

                # Get properties for this propstat
                prop = ElementsByName(props, "DAV:", "prop")
                if len(prop) != 1:
                    return False, "           Wrong number of DAV:prop elements\n"

                for child in prop[0]._get_childNodes():
                    if isinstance(child, Element):
                        qname = (child.namespaceURI, child.localName)
                        fqname = qname[0] + qname[1]
                        if child.firstChild is not None:
                            # Copy sub-element data as text into one long string and strip leading/trailing space
                            value = ""
                            for p in child._get_childNodes():
                                temp = p.toprettyxml("", "")
                                temp = temp.strip()
                                value += temp
                        else:
                            value = ""
                        
                        if fqname == propertyname:
                            return value

        return None