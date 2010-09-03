##
# Copyright (c) 2010 Apple Inc. All rights reserved.
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
Verifier that checks the response body for an exact match to data in a file.
"""

from xml.etree.ElementTree import ElementTree
import StringIO

class Verifier(object):
    
    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable
        # Get arguments
        exists = args.get("exists", [])
        notexists = args.get("notexists", [])
 
        # status code must be 200, 207
        if response.status not in (200,207):
            return False, "        HTTP Status Code Wrong: %d" % (response.status,)
        
        # look for response data
        if not respdata:
            return False, "        No response body"
                
        # Read in XML
        try:
            tree = ElementTree(file=StringIO.StringIO(respdata))
        except Exception, e:
            return False, "        Response data is not xml data: %s" % (e,)
        
        def _splitPathTests(path):
            if '[' in path:
                return path.split('[', 1)
            else:
                return path, None
            
        result = True
        resulttxt = ""
        for path in exists:
            if '[' in path:
                actual_path, tests = path.split('[', 1)
            else:
                actual_path = path
                tests = None
            
            # Handle absolute root element
            if actual_path[0] == '/':
                actual_path = actual_path[1:]
            if '/' in actual_path:
                root_path, child_path = actual_path.split('/', 1)
                if tree.getroot().tag != root_path:
                    resulttxt += "        Items not returned in XML for %s\n" % (path,)
                node = tree.find(child_path)
            else:
                root_path = actual_path
                child_path = None
                node = tree.getroot()
            
            if node is None:
                resulttxt += "        Items not returned in XML for %s\n" % (path,)
                result = False
                continue
            if tests:
                tests = [item[:-1] for item in tests.split('[')]
                for test in tests:
                    if test[0] == '@':
                        if '=' in test:
                            attr, value = test[1:].split('=')
                            value = value[1:-1]
                        else:
                            attr = test[1:]
                            value = None
                        if attr not in node.keys():
                            resulttxt += "        Missing attribute returned in XML for %s\n" % (path,)
                            result = False
                            break
                        if value is not None and node.get(attr) != value:
                            resulttxt += "        Incorrect attribute value returned in XML for %s\n" % (path,)
                            result = False
                            break
                    elif test[0] == '=':
                        if node.text != test[1:]:
                            resulttxt += "        Incorrect value returned in XML for %s\n" % (path,)
                            
        for path in notexists:
            if tree.find(path) is not None:
                resulttxt += "        Items returned in XML for %s: %s\n" % (path,)
                result = False
            
                
        return result, resulttxt
        