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
Defines the 'request' class which encapsulates an HTTP request and verification.
"""

import base64
import src.xmlDefs
import time

class request( object ):
    """
    Represents the HTTP request to be executed, and verifcation information to
    be used to determine a satisfactory output or not.
    """
    __slots__  = ['manager', 'auth', 'user', 'pswd', 'end_delete', 'print_response',
                  'method', 'headers', 'ruri', 'data', 'datasubs', 'verifiers', 'grablocation']
    
    def __init__( self, manager ):
        self.manager = manager
        self.auth = True
        self.user = ""
        self.pswd = ""
        self.end_delete = False
        self.print_response = False
        self.method = ""
        self.headers = {}
        self.ruri = ""
        self.data = None
        self.datasubs = True
        self.verifiers = []
        self.grablocation = False
    
    def __str__(self):
        return "Method: %s; uri: %s" % (self.method, self.ruri)

    def getURI( self, si ):
        if self.ruri == "$":
            return self.ruri
        if len(self.ruri) > 0 and self.ruri[0] == '/':
            uri = ""
        else:
            uri = "%s/" % ( si.calendarpath )
        uri += self.ruri
        return uri
        
    def getHeaders( self, si ):
        hdrs = self.headers
        
        # Content type
        if self.data != None:
            hdrs["Content-Type"] = self.data.content_type
        
        # Auth
        if self.auth:
            hdrs["Authorization"] = self.gethttpauth( si )
        
        return hdrs

    def gethttpauth( self, si ):
        basicauth = [self.user, si.user][self.user == ""]
        basicauth += ":"
        basicauth += [self.pswd, si.pswd][self.pswd == ""]
        basicauth = "Basic " + base64.encodestring( basicauth )
        basicauth = basicauth.replace( "\n", "" )
        return basicauth

    def getFilePath( self ):
        if self.data != None:
            return self.data.filepath
        else:
            return ""

    def getData( self ):
        data = ""
        if self.data != None:
            if len(self.data.value) != 0:
                data = self.data.value
            else:
                # read in the file data
                fd = open( self.data.filepath, "r" )
                try:
                    data = fd.read()
                finally:
                    fd.close()
            if self.datasubs:
                data = str(self.manager.server_info.subs(data))
        return data
    
    def parseXML( self, node ):
        self.auth = node.getAttribute( src.xmlDefs.ATTR_AUTH ) != src.xmlDefs.ATTR_VALUE_NO
        self.user = self.manager.server_info.subs(node.getAttribute( src.xmlDefs.ATTR_USER ))
        self.pswd = self.manager.server_info.subs(node.getAttribute( src.xmlDefs.ATTR_PSWD ))
        self.end_delete = node.getAttribute( src.xmlDefs.ATTR_END_DELETE ) == src.xmlDefs.ATTR_VALUE_YES
        self.print_response = node.getAttribute( src.xmlDefs.ATTR_PRINT_RESPONSE ) == src.xmlDefs.ATTR_VALUE_YES

        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_METHOD:
                self.method = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_HEADER:
                self.parseHeader(child)
            elif child._get_localName() == src.xmlDefs.ELEMENT_RURI:
                self.ruri = self.manager.server_info.subs(child.firstChild.data)
            elif child._get_localName() == src.xmlDefs.ELEMENT_DATA:
                self.data = data()
                self.datasubs = self.data.parseXML( child )
            elif child._get_localName() == src.xmlDefs.ELEMENT_VERIFY:
                self.verifiers.append(verify(self.manager))
                self.verifiers[-1].parseXML( child )
            elif child._get_localName() == src.xmlDefs.ELEMENT_GRABLOCATION:
                self.grablocation = True

    def parseHeader(self, node):
        
        name = None
        value = None
        for child in node._get_childNodes():
           if child._get_localName() == src.xmlDefs.ELEMENT_NAME:
                name = child.firstChild.data
           elif child._get_localName() == src.xmlDefs.ELEMENT_VALUE:
                value = self.manager.server_info.subs(child.firstChild.data)
        
        if (name is not None) and (value is not None):
            self.headers[name] = value
            
    def parseList( manager, node ):
        requests = []
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_REQUEST:
                req = request(manager)
                req.parseXML( child )
                requests.append( req )
        return requests
                
    parseList = staticmethod( parseList )

class data( object ):
    """
    Represents the data/body portion of an HTTP request.
    """
    __slots__  = ['content_type', 'filepath', 'value']
    
    def __init__( self ):
        self.content_type = ""
        self.filepath = ""
        self.value = ""
    
    def parseXML( self, node ):

        subs = node.getAttribute( src.xmlDefs.ATTR_SUBSTITUTIONS ) != src.xmlDefs.ATTR_VALUE_NO

        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_CONTENTTYPE:
                self.content_type = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_FILEPATH:
                self.filepath = child.firstChild.data

        return subs

class verify( object ):
    """
    Defines how the result of a request should be verified. This is done
    by passing the response and response data to a callback with a set of arguments
    specified in the test XML config file. The callback name is in the XML config
    file also and is dynamically loaded to do the verification.
    """
    __slots__  = ['manager', 'callback', 'args']
    
    def __init__( self, manager ):
        self.manager = manager
        self.callback = None
        self.args = {}
    
    def doVerify(self, uri, response, respdata):
        verifierClass = self._importName("verifiers." + self.callback, "Verifier")
        verifier = verifierClass()
        return verifier.verify(self.manager, uri, response, respdata, self.args)

    def _importName(self, modulename, name):
        """
        Import a named object from a module in the context of this function.
        """
        module = __import__(modulename, globals( ), locals( ), [name])
        return getattr(module, name)

    def parseXML( self, node ):

        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_CALLBACK:
                self.callback = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_ARG:
                self.parseArgXML(child)

    def parseArgXML(self, node):
        name = None
        values = []
        for child in node._get_childNodes():
            if child._get_localName() == src.xmlDefs.ELEMENT_NAME:
                name = child.firstChild.data
            elif child._get_localName() == src.xmlDefs.ELEMENT_VALUE:
                if child.firstChild is not None:
                    values.append(self.manager.server_info.subs(child.firstChild.data))
                else:
                    values.append("")
        if name and len(values):
            self.args[name] = values

class stats( object ):
    """
    Maintains stats about the current test.
    """
    __slots__ = ['count', 'totaltime', 'currenttime']
    
    def __init__(self):
        self.count = 0
        self.totaltime = 0.0
        self.currenttime = 0.0
        
    def startTimer(self):
        self.currenttime = time.time()
        
    def endTimer(self):
        self.count += 1
        self.totaltime += time.time() - self.currenttime
