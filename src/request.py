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
Defines the 'request' class which encapsulates an HTTP request and verification.
"""

from hashlib import md5, sha1
from src.xmlUtils import getYesNoAttributeValue
import base64
import httplib
import src.xmlDefs
import time

algorithms = {
    'md5': md5,
    'md5-sess': md5,
    'sha': sha1,
}

# DigestCalcHA1
def calcHA1(
    pszAlg,
    pszUserName,
    pszRealm,
    pszPassword,
    pszNonce,
    pszCNonce,
    preHA1=None
):
    """
    @param pszAlg: The name of the algorithm to use to calculate the digest.
        Currently supported are md5 md5-sess and sha.

    @param pszUserName: The username
    @param pszRealm: The realm
    @param pszPassword: The password
    @param pszNonce: The nonce
    @param pszCNonce: The cnonce

    @param preHA1: If available this is a str containing a previously
       calculated HA1 as a hex string. If this is given then the values for
       pszUserName, pszRealm, and pszPassword are ignored.
    """

    if (preHA1 and (pszUserName or pszRealm or pszPassword)):
        raise TypeError(("preHA1 is incompatible with the pszUserName, "
                         "pszRealm, and pszPassword arguments"))

    if preHA1 is None:
        # We need to calculate the HA1 from the username:realm:password
        m = algorithms[pszAlg]()
        m.update(pszUserName)
        m.update(":")
        m.update(pszRealm)
        m.update(":")
        m.update(pszPassword)
        HA1 = m.digest()
    else:
        # We were given a username:realm:password
        HA1 = preHA1.decode('hex')

    if pszAlg == "md5-sess":
        m = algorithms[pszAlg]()
        m.update(HA1)
        m.update(":")
        m.update(pszNonce)
        m.update(":")
        m.update(pszCNonce)
        HA1 = m.digest()

    return HA1.encode('hex')

# DigestCalcResponse
def calcResponse(
    HA1,
    algo,
    pszNonce,
    pszNonceCount,
    pszCNonce,
    pszQop,
    pszMethod,
    pszDigestUri,
    pszHEntity,
):
    m = algorithms[algo]()
    m.update(pszMethod)
    m.update(":")
    m.update(pszDigestUri)
    if pszQop == "auth-int":
        m.update(":")
        m.update(pszHEntity)
    HA2 = m.digest().encode('hex')

    m = algorithms[algo]()
    m.update(HA1)
    m.update(":")
    m.update(pszNonce)
    m.update(":")
    if pszNonceCount and pszCNonce and pszQop:
        m.update(pszNonceCount)
        m.update(":")
        m.update(pszCNonce)
        m.update(":")
        m.update(pszQop)
        m.update(":")
    m.update(HA2)
    respHash = m.digest().encode('hex')
    return respHash

class request( object ):
    """
    Represents the HTTP request to be executed, and verifcation information to
    be used to determine a satisfactory output or not.
    """
    __slots__  = ['manager', 'auth', 'user', 'pswd', 'end_delete', 'print_response',
                  'method', 'headers', 'ruris', 'ruri', 'data', 'datasubs', 'verifiers',
                  'grabheader', 'grabproperty', 'grabelement', 'require_features']
    
    def __init__( self, manager ):
        self.manager = manager
        self.auth = True
        self.user = ""
        self.pswd = ""
        self.end_delete = False
        self.print_response = False
        self.require_features = set()
        self.method = ""
        self.headers = {}
        self.ruris = []
        self.ruri = ""
        self.data = None
        self.datasubs = True
        self.verifiers = []
        self.grabheader = []
        self.grabproperty = []
        self.grabelement = []
    
    def __str__(self):
        return "Method: %s; uris: %s" % (self.method, self.ruris if len(self.ruris) > 1 else self.ruri,)

    def missingFeatures(self):
        return self.require_features - self.manager.server_info.features

    def getURI( self, si ):
        return si.extrasubs(self.ruri)
        
    def getHeaders( self, si ):
        hdrs = self.headers
        for key, value in hdrs.items():
            hdrs[key] = si.extrasubs(value)
        
        # Content type
        if self.data != None:
            hdrs["Content-Type"] = self.data.content_type
        
        # Auth
        if self.auth:
            if si.authtype.lower() == "digest":
                hdrs["Authorization"] = self.gethttpdigestauth( si )
            else:
                hdrs["Authorization"] = self.gethttpbasicauth( si )
        
        return hdrs

    def gethttpbasicauth( self, si ):
        basicauth = [self.user, si.user][self.user == ""]
        basicauth += ":"
        basicauth += [self.pswd, si.pswd][self.pswd == ""]
        basicauth = "Basic " + base64.encodestring( basicauth )
        basicauth = basicauth.replace( "\n", "" )
        return basicauth

    def gethttpdigestauth( self, si, wwwauthorize=None ):
        
        # Check the nonce cache to see if we've used this user before
        user = [self.user, si.user][self.user == ""]
        pswd = [self.pswd, si.pswd][self.pswd == ""]
        details = None
        if self.manager.digestCache.has_key(user):
            details = self.manager.digestCache[user]
        else:
            if si.ssl:
                http = httplib.HTTPSConnection( self.manager.server_info.host, self.manager.server_info.port )
            else:
                http = httplib.HTTPConnection( self.manager.server_info.host, self.manager.server_info.port )
            try:
                http.request( "OPTIONS", self.getURI(si) )
            
                response = http.getresponse()
    
            finally:
                http.close()

            if response.status == 401:

                wwwauthorize = response.msg.getheaders("WWW-Authenticate")
                for item in wwwauthorize:
                    if not item.startswith("digest "):
                        continue
                    wwwauthorize = item[7:]
                    def unq(s):
                        if s[0] == s[-1] == '"':
                            return s[1:-1]
                        return s
                    parts = wwwauthorize.split(',')
            
                    details = {}
        
                    for (k, v) in [p.split('=', 1) for p in parts]:
                        details[k.strip()] = unq(v.strip())
                        
                    self.manager.digestCache[user] = details
                    break

        if details:
            digest = calcResponse(
                calcHA1(details.get('algorithm'), user, details.get('realm'), pswd, details.get('nonce'), details.get('cnonce')),
                details.get('algorithm'), details.get('nonce'), details.get('nc'), details.get('cnonce'), details.get('qop'), self.method, self.getURI(si), None
            )
    
            if details.get('qop'):
                response = ('Digest username="%s", realm="%s", '
                        'nonce="%s", uri="%s", '
                        'response=%s, algorithm=%s, cnonce="%s", qop=%s, nc=%s' % (user, details.get('realm'), details.get('nonce'), self.getURI(si), digest, details.get('algorithm'), details.get('cnonce'), details.get('qop'), details.get('nc'), ))
            else:
                response = ('Digest username="%s", realm="%s", '
                        'nonce="%s", uri="%s", '
                        'response=%s, algorithm=%s' % (user, details.get('realm'), details.get('nonce'), self.getURI(si), digest, details.get('algorithm'), ))
    
            return response
        else:
            return ""

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
                data = self.manager.server_info.extrasubs(data)
        return data
    
    def parseXML( self, node ):
        self.auth = node.get(src.xmlDefs.ATTR_AUTH, src.xmlDefs.ATTR_VALUE_YES) == src.xmlDefs.ATTR_VALUE_YES
        self.user = self.manager.server_info.subs(node.get(src.xmlDefs.ATTR_USER, "").encode("utf-8"))
        self.pswd = self.manager.server_info.subs(node.get(src.xmlDefs.ATTR_PSWD, "").encode("utf-8"))
        self.end_delete = getYesNoAttributeValue(node, src.xmlDefs.ATTR_END_DELETE)
        self.print_response = getYesNoAttributeValue(node, src.xmlDefs.ATTR_PRINT_RESPONSE)

        for child in node.getchildren():
            if child.tag == src.xmlDefs.ELEMENT_REQUIRE_FEATURE:
                self.parseFeatures( child )
            elif child.tag == src.xmlDefs.ELEMENT_METHOD:
                self.method = child.text.encode("utf-8")
            elif child.tag == src.xmlDefs.ELEMENT_HEADER:
                self.parseHeader(child)
            elif child.tag == src.xmlDefs.ELEMENT_RURI:
                self.ruris.append(self.manager.server_info.subs(child.text.encode("utf-8")))
                if len(self.ruris) == 1:
                    self.ruri = self.ruris[0]
            elif child.tag == src.xmlDefs.ELEMENT_DATA:
                self.data = data()
                self.datasubs = self.data.parseXML( child )
            elif child.tag == src.xmlDefs.ELEMENT_VERIFY:
                self.verifiers.append(verify(self.manager))
                self.verifiers[-1].parseXML( child )
            elif child.tag == src.xmlDefs.ELEMENT_GRABHEADER:
                self.parseGrab(child, self.grabheader)
            elif child.tag == src.xmlDefs.ELEMENT_GRABPROPERTY:
                self.parseGrab(child, self.grabproperty)
            elif child.tag == src.xmlDefs.ELEMENT_GRABELEMENT:
                self.parseGrab(child, self.grabelement)

    def parseFeatures(self, node):
        for child in node.getchildren():
            if child.tag == src.xmlDefs.ELEMENT_FEATURE:
                self.require_features.add(child.text.encode("utf-8"))

    def parseHeader(self, node):
        
        name = None
        value = None
        for child in node.getchildren():
            if child.tag == src.xmlDefs.ELEMENT_NAME:
                name = child.text.encode("utf-8")
            elif child.tag == src.xmlDefs.ELEMENT_VALUE:
                value = self.manager.server_info.subs(child.text.encode("utf-8"))
        
        if (name is not None) and (value is not None):
            self.headers[name] = value
            
    def parseList( manager, node ):
        requests = []
        for child in node.getchildren():
            if child.tag == src.xmlDefs.ELEMENT_REQUEST:
                req = request(manager)
                req.parseXML( child )
                requests.append( req )
        return requests
                
    parseList = staticmethod( parseList )

    def parseGrab(self, node, appendto):
        
        name = None
        variable = None
        for child in node.getchildren():
            if child.tag in (src.xmlDefs.ELEMENT_NAME, src.xmlDefs.ELEMENT_PROPERTY):
                name = child.text.encode("utf-8")
            elif child.tag == src.xmlDefs.ELEMENT_VARIABLE:
                variable = self.manager.server_info.subs(child.text.encode("utf-8"))
        
        if (name is not None) and (variable is not None):
            appendto.append((name, variable))
            
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

        subs = node.get(src.xmlDefs.ATTR_SUBSTITUTIONS, src.xmlDefs.ATTR_VALUE_YES) == src.xmlDefs.ATTR_VALUE_YES

        for child in node.getchildren():
            if child.tag == src.xmlDefs.ELEMENT_CONTENTTYPE:
                self.content_type = child.text.encode("utf-8")
            elif child.tag == src.xmlDefs.ELEMENT_FILEPATH:
                self.filepath = child.text.encode("utf-8")

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
        
        # Re-do substitutions from values generated during the current test run
        if self.manager.server_info.hasextrasubs():
            for name, values in self.args.iteritems():
                newvalues = [self.manager.server_info.extrasubs(value) for value in values]
                self.args[name] = newvalues
                
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

        for child in node.getchildren():
            if child.tag == src.xmlDefs.ELEMENT_CALLBACK:
                self.callback = child.text.encode("utf-8")
            elif child.tag == src.xmlDefs.ELEMENT_ARG:
                self.parseArgXML(child)

    def parseArgXML(self, node):
        name = None
        values = []
        for child in node.getchildren():
            if child.tag == src.xmlDefs.ELEMENT_NAME:
                name = child.text.encode("utf-8")
            elif child.tag == src.xmlDefs.ELEMENT_VALUE:
                if child.text is not None:
                    values.append(self.manager.server_info.subs(child.text.encode("utf-8")))
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
