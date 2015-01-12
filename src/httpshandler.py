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
    "This class allows communication via SSL."

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

def SmartHTTPConnection(host, port, ssl):

    def trySSL(version):
        connect = HTTPSVersionConnection(host, port, ssl_version=version)
        connect.connect()
        return connect

    if ssl:
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
