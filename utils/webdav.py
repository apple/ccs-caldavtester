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
Class to carry out common WebDAV operations.
"""
import base64
import urllib

import httplib
import xml.dom.minidom

class WebDAVRequest(object):
    """
    Class that encapsulates the details of a request.
    """

    __slots__ = ['host', 'port', 'method', 'uri', 'user', 'pswd', 'headers', 'body']
    
    def __init__(self, **kwargs):
        self.host = kwargs.get("host", "")
        self.port = kwargs.get("port", 80)
        self.method = kwargs.get("method", "OPTIONS")
        self.uri = kwargs.get("uri", "/")
        self.user = kwargs.get("user", None)
        self.pswd = kwargs.get("pswd", None)
        self.headers = kwargs.get("headers", {})
        self.body = kwargs.get("body", None)

    def execute(self):

        # Do the http request
        http = httplib.HTTPConnection( self.host, self.port )
        try:
            http.request( self.method, urllib.quote(self.uri), self.body, self.getHeaders() )
        
            response = http.getresponse()
        
            respdata = response.read()

        finally:
            http.close()
        
        return response.status, respdata

    def getHeaders( self ):
        hdrs = self.headers
        
        # Auth
        if self.user:
            hdrs["Authorization"] = self.gethttpauth( )
        
        return hdrs

    def gethttpauth( self ):
        basicauth = self.user
        basicauth += ":"
        basicauth += self.pswd
        basicauth = "Basic " + base64.encodestring( basicauth )
        basicauth = basicauth.replace( "\n", "" )
        return basicauth

class ResourceExists(WebDAVRequest):
    """
    Tests whether the specified resource exists.
    """
    
    propfind = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
<D:resourcetype/>
<D:getetag/>
</D:prop>
</D:propfind>
"""

    def __init__(self, serverinfo, uri):
        super(ResourceExists, self).__init__(host=serverinfo.host, port=serverinfo.port, user=serverinfo.user, pswd=serverinfo.pswd, method="PROPFIND", uri=uri, body=self.propfind)
        
    def run(self):
        status, resp = self.execute() #@UnusedVariable
        return status == httplib.MULTI_STATUS
    
    def isfile(self):
        return not self.iscollection()

    def iscollection(self):
        status, resp = self.execute()
        if status == httplib.MULTI_STATUS:
            doc = xml.dom.minidom.parse( resp )
            multistatus = doc._get_documentElement()
            for iter in multistatus.getElementsByTagNameNS( "DAV:", "resourcetype" ):
                return iter.firstChild.data.find("collection") != -1

        return False

class MakeCollection(WebDAVRequest):
    
    def __init__(self, serverinfo, uri):
        super(MakeCollection, self).__init__(host=serverinfo.host, port=serverinfo.port, user=serverinfo.user, pswd=serverinfo.pswd, method="MKCOL", uri=uri)
        
    def run(self):
        status, resp = self.execute() #@UnusedVariable
        return status/100 == 2

class MakeCalendar(WebDAVRequest):
    
    def __init__(self, serverinfo, uri):
        super(MakeCalendar, self).__init__(host=serverinfo.host, port=serverinfo.port, user=serverinfo.user, pswd=serverinfo.pswd, method="MKCALENDAR", uri=uri)
        
    def run(self):
        status, resp = self.execute() #@UnusedVariable
        return status/100 == 2

class Put(WebDAVRequest):
    
    def __init__(self, serverinfo, uri, content, data):
        hdrs = {"Content-Type": content}
        super(Put, self).__init__(host=serverinfo.host, port=serverinfo.port, user=serverinfo.user, pswd=serverinfo.pswd, method="PUT", uri=uri, headers=hdrs, body=data)
        
    def run(self):
        status, resp = self.execute() #@UnusedVariable
        return status/100 == 2

class Delete(WebDAVRequest):
    
    def __init__(self, serverinfo, uri):
        super(Delete, self).__init__(host=serverinfo.host, port=serverinfo.port, user=serverinfo.user, pswd=serverinfo.pswd, method="DELETE", uri=uri)
        
    def run(self):
        status, resp = self.execute() #@UnusedVariable
        return status/100 == 2
        
