##
# Copyright (c) 2010-2015 Apple Inc. All rights reserved.
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

import httplib
import socket
import ssl as sslmodule

class HTTPSVersionConnection(httplib.HTTPSConnection):
    """
    An L{httplib.HTTPSConnection} class that allows the TLS protocol version to be set.
    """

    def __init__(self, host, port, ssl_version=sslmodule.PROTOCOL_TLSv1):
        httplib.HTTPSConnection.__init__(self, host, port)
        self._ssl_version = ssl_version


    def connect(self):
        "Connect to a host on a given (SSL) port."

        sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock = sslmodule.wrap_socket(sock, self.key_file, self.cert_file, ssl_version=self._ssl_version)


cached_types = (
    (set(), sslmodule.PROTOCOL_TLSv1),
    (set(), sslmodule.PROTOCOL_SSLv3),
    (set(), sslmodule.PROTOCOL_SSLv23),
)

class UnixSocketHTTPConnection(httplib.HTTPConnection):
    """
    An L{httplib.HTTPConnection} class that uses a unix socket rather than TCP.
    """

    def __init__(self, path, host, port):
        httplib.HTTPConnection.__init__(self, host, port)
        self.path = path


    def connect(self):
        """
        Connect using the supplied unix socket file path
        """
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)



def SmartHTTPConnection(host, port, ssl, afunix):
    """
    Create the appropriate L{httplib.HTTPConnection} derived class for the supplied arguments.

    @param host: TCP host name
    @type host: L{str}
    @param port: TCP port number
    @type port: L{int}
    @param ssl: indicates if SSL is to be used
    @type ssl: L{bool}
    @param afunix: unix socket to use or L{None}
    @type afunix: L{str}
    """

    def trySSL(version):
        connect = HTTPSVersionConnection(host, port, ssl_version=version)
        connect.connect()
        return connect

    if afunix:
        connect = UnixSocketHTTPConnection(afunix, host, port)
    elif ssl:
        # Iterate over the TL:S versions and find one that works and cache it for future use.
        for cached, connection_type in cached_types:
            if (host, port) in cached:
                try:
                    return trySSL(connection_type)
                except:
                    cached.remove((host, port))

        for cached, connection_type in cached_types:
            try:
                cached.add((host, port))
                return trySSL(connection_type)
            except:
                cached.remove((host, port))

        raise RuntimeError("Cannot connect via with TLSv1, SSLv3 or SSLv23")
    else:
        connect = httplib.HTTPConnection(host, port)
    connect.connect()
    return connect
