##
# Copyright (c) 2006 Apple Computer, Inc. All rights reserved.
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

"""
Class to encapsulate a single caldav test run.
"""

from src.manager import manager
from src.request import data
from src.request import request
from src.request import stats
from src.testsuite import testsuite
from xml.dom.minicompat import NodeList
from xml.dom.minidom import Node
import httplib
import os
import rfc822
import socket
import src.xmlDefs
import time
import xattr
import xml.dom.minidom

STATUSTXT_WIDTH    = 60

class caldavtest(object):
    __slots__  = ['manager', 'name', 'description', 'ignore_all', 'start_requests', 'end_requests', 'end_deletes', 'suites', 'grabbedlocation']
    
    def __init__( self, manager, name ):
        self.manager = manager
        self.name = name
        self.description = ""
        self.ignore_all = False
        self.start_requests = []
        self.end_requests = []
        self.end_deletes = []
        self.suites = []
        self.grabbedlocation = None
        
    def run( self ):
        try:
            self.manager.log(manager.LOG_HIGH, "----- Running CalDAV Tests from \"%s\"... -----" % self.name, before=1)
            self.dorequests( "Executing Start Requests...", self.start_requests, False, True )
            ok, failed, ignored = self.run_tests()
            self.doenddelete( "Deleting Requests..." )
            self.dorequests( "Executing End Requests...", self.end_requests, False )
            return ok, failed, ignored
        except socket.error, msg:
            self.manager.log(manager.LOG_HIGH, "FATAL ERROR: " + msg.args[1], before=2)
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
        else:
            self.manager.log(manager.LOG_HIGH, "")
            for test in suite.tests:
                result = self.run_test( test )
                if result == "t":
                    ok += 1
                elif result == "f":
                    failed += 1
                else:
                    ignored += 1
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
            if test.stats:
                reqstats = stats()
            else:
                reqstats = None
            for ctr in range(test.count): #@UnusedVariable
                for req in test.requests:
                    result, resulttxt, response, respdata = self.dorequest( req, test.details, True, False, reqstats )
                    if not result:
                        break
            self.manager.log(manager.LOG_HIGH, ["[FAILED]", "[OK]"][result])
            if len(resulttxt) > 0:
                self.manager.log(manager.LOG_HIGH, resulttxt)
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
            result, resulttxt, response, respdata = self.dorequest( req, False, doverify, forceverify )
            if not result:
                resulttxt += "\nFailure during multiple requests #%d out of %d, request=%s" % (ctr, len(list), str(req))
                break
            ctr += 1
        self.manager.log(manager.LOG_HIGH, ["[FAILED]", "[OK]"][result])
        if len(resulttxt) > 0:
            self.manager.log(manager.LOG_HIGH, resulttxt)
        return result
    
    def dofindall( self, collection):
        hrefs = []
        req = request()
        req.method = "PROPFIND"
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
        result, resulttxt, response, respdata = self.dorequest( req, False, False )
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
            req = request()
            req.method = "DELETE"
            req.ruri = deleter[0]
            if len(deleter[1]):
                req.user = deleter[1]
            if len(deleter[2]):
                req.pswd = deleter[2]
            self.dorequest( req, False, False )

    def dofindnew( self, collection):
        hresult = ""
        req = request()
        req.method = "PROPFIND"
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
        result, resulttxt, response, respdata = self.dorequest( req, False, False )
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
            req = request()
            req.method = "DELETE"
            req.ruri = deleter[0]
            if len(deleter[1]):
                req.user = deleter[1]
            if len(deleter[2]):
                req.pswd = deleter[2]
            self.dorequest( req, False, False )
        self.manager.log(manager.LOG_HIGH, "[DONE]")
    
    def doaccess(self, ruri, enable):
        """
        We have to set the xattr WebDAV:{http:%2F%2Ftwistedmatrix.com%2Fxml_namespace%2Fdav%2Fprivate%2F}access-disabled 
        on the resource pointed to by the ruri. Strictly speaking only the server know how to map from a uri to a file
        path, so we have to cheat!
        """
        if self.manager.server_info.serverfilepath:
            filename = os.path.join(self.manager.server_info.serverfilepath, ruri[1:])
            if os.path.exists(filename):
                attrs = xattr.xattr(filename)
                if enable:
                    del attrs["WebDAV:{http:%2F%2Ftwistedmatrix.com%2Fxml_namespace%2Fdav%2Fprivate%2F}caldav-access-disabled"]
                else:
                    attrs["WebDAV:{http:%2F%2Ftwistedmatrix.com%2Fxml_namespace%2Fdav%2Fprivate%2F}caldav-access-disabled"] = "yes"
                return True
        return False

    def doquota(self, ruri, size):
        """
        We have to set the xattr WebDAV:{http:%2F%2Ftwistedmatrix.com%2Fxml_namespace%2Fdav%2Fprivate%2F}access-disabled 
        on the resource pointed to by the ruri. Strictly speaking only the server know how to map from a uri to a file
        path, so we have to cheat!
        """
        if self.manager.server_info.serverfilepath:
            filename = os.path.join(self.manager.server_info.serverfilepath, ruri[1:])
            if os.path.exists(filename):
                attrs = xattr.xattr(filename)
                if size is None:
                    del attrs["WebDAV:{http:%2F%2Ftwistedmatrix.com%2Fxml_namespace%2Fdav%2Fprivate%2F}quota-root"]
                else:
                    attrs["WebDAV:{http:%2F%2Ftwistedmatrix.com%2Fxml_namespace%2Fdav%2Fprivate%2F}quota-root"] = \
                            "<?xml version='1.0' encoding='UTF-8'?>\n" + \
                            "<quota-root xmlns='http://twistedmatrix.com/xml_namespace/dav/private/'>" + \
                            str(size) + \
                            "</quota-root>"
                return True
        return False

    def dorequest( self, req, details=False, doverify = True, forceverify = False, stats = None ):
        
        # Special check for DELETEALL
        if req.method == "DELETEALL":
            collection = (req.ruri, req.user, req.pswd)
            hrefs = self.dofindall(collection)
            self.dodeleteall(hrefs)
            return True, "", None, None
        
        # Special check for ACCESS-DISABLE
        if req.method == "ACCESS-DISABLE":
            if self.doaccess(req.ruri, False):
                return True, "", None, None
            else:
                return False, "Could not set caldav-access-disabled xattr on file", None, None
        elif req.method == "ACCESS-ENABLE":
            if self.doaccess(req.ruri, True):
                return True, "", None, None
            else:
                return False, "Could not remove caldav-access-disabled xattr on file", None, None

        # Special check for QUOTA
        if req.method == "QUOTA-DISABLE":
            if self.doquota(req.ruri, None):
                return True, "", None, None
            else:
                return False, "Could remove quota-root xattr on file", None, None
        elif req.method.startswith("QUOTA-ENABLE-"):
            if self.doquota(req.ruri, req.method[len("QUOTA-ENABLE-"):]):
                return True, "", None, None
            else:
                return False, "Could not set quota-root xattr on file", None, None

        # Special for delay
        if req.method == "DELAY":
            # self.ruri contains a numeric delay in seconds
            delay = int(req.ruri)
            starttime = time.time()
            while (time.time() < starttime + delay):
                pass
            return True, "", None, None

        # Special for LISTNEW
        if req.method == "LISTNEW":
            collection = (req.ruri, req.user, req.pswd)
            self.grabbedlocation = self.dofindnew(collection)
            return True, "", None, None
            
        # Special for GETNEW
        if req.method == "GETNEW":
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
        
        if req.grablocation:
            hdrs = response.msg.getheaders("Location")
            if hdrs:
                self.grabbedlocation = hdrs[0]

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
            elif child._get_localName() == src.xmlDefs.ELEMENT_START:
                self.start_requests = request.parseList( self.manager, child )
            elif child._get_localName() == src.xmlDefs.ELEMENT_TESTSUITE:
                suite = testsuite(self.manager)
                suite.parseXML( child )
                self.suites.append( suite )
            elif child._get_localName() == src.xmlDefs.ELEMENT_END:
                self.end_requests = request.parseList( self.manager, child )
    
