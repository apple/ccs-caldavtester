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


"""
Verifier that checks the response body for an exact match to data in a file.
"""

from pycalendar.icalendar.calendar import Calendar
from xml.etree.cElementTree import ElementTree
import json
import re
import StringIO

class Verifier(object):

    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable
        # Get arguments
        parent = args.get("parent", [])
        exists = args.get("exists", [])
        notexists = args.get("notexists", [])

        # status code must be 200, 207
        if response.status not in (200, 207):
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

        if parent:
            nodes = self.nodeForPath(tree.getroot(), parent[0])
            if len(nodes) == 0:
                return False, "        Response data is missing parent node: %s" % (parent[0],)
            elif len(nodes) > 1:
                return False, "        Response data has too many parent nodes: %s" % (parent[0],)
            root = nodes[0]
        else:
            root = tree.getroot()

        result = True
        resulttxt = ""
        for path in exists:

            matched, txt = self.matchNode(root, path)
            result &= matched
            resulttxt += txt

        for path in notexists:
            matched, _ignore_txt = self.matchNode(root, path)
            if matched:
                resulttxt += "        Items returned in XML for %s\n" % (path,)
                result = False

        return result, resulttxt


    def nodeForPath(self, root, path):
        if '[' in path:
            actual_path, tests = path.split('[', 1)
        else:
            actual_path = path
            tests = None

        # Handle absolute root element
        if actual_path[0] == '/':
            actual_path = actual_path[1:]
        r = re.search("(\{[^\}]+\}[^/]+)(.*)", actual_path)
        if r.group(2):
            root_path = r.group(1)
            child_path = r.group(2)[1:]
            if root.tag != root_path:
                return None
            nodes = root.findall(child_path)
        else:
            root_path = actual_path
            child_path = None
            nodes = (root,)

        if len(nodes) == 0:
            return None

        results = []

        if tests:
            tests = [item[:-1] for item in tests.split('[')]
            for test in tests:
                for node in nodes:
                    testresult = self.testNode(node, path, test)
                    if testresult is None:
                        results.append(node)
        else:
            results = nodes

        return results


    @classmethod
    def testNode(cls, node, node_path, test):
        result = None
        if test[0] == '@':
            if '=' in test:
                attr, value = test[1:].split('=')
                value = value[1:-1]
            else:
                attr = test[1:]
                value = None
            if attr not in node.keys():
                result = "        Missing attribute returned in XML for %s\n" % (node_path,)
            if value is not None and node.get(attr) != value:
                result = "        Incorrect attribute value returned in XML for %s\n" % (node_path,)
        elif test[0] == '=':
            if node.text != test[1:]:
                result = "        Incorrect value returned in XML for %s\n" % (node_path,)
        elif test[0] == '!':
            if node.text == test[1:]:
                result = "        Incorrect value returned in XML for %s\n" % (node_path,)
        elif test[0] == '*':
            if node.text is None or node.text.find(test[1:]) == -1:
                result = "        Incorrect value returned in XML for %s\n" % (node_path,)
        elif test[0] == '$':
            if node.text is None or node.text.find(test[1:]) != -1:
                result = "        Incorrect value returned in XML for %s\n" % (node_path,)
        elif test[0] == '+':
            if node.text is None or not node.text.startswith(test[1:]):
                result = "        Incorrect value returned in XML for %s\n" % (node_path,)
        elif test[0] == '^':
            if "=" in test:
                element, value = test[1:].split("=", 1)
            else:
                element = test[1:]
                value = None
            for child in node.getchildren():
                if child.tag == element and (value is None or child.text == value):
                    break
            else:
                result = "        Missing child returned in XML for %s\n" % (node_path,)
        elif test[0] == '|':
            if len(test) == 2 and test[1] == "|":
                if node.text is None and len(node.getchildren()) == 0:
                    result = "        Empty element returned in XML for %s\n" % (node_path,)
            else:
                if node.text is not None or len(node.getchildren()) != 0:
                    result = "        Non-empty element returned in XML for %s\n" % (node_path,)

        # Try to parse as iCalendar
        elif test == 'icalendar':
            try:
                Calendar.parseText(node.text)
            except:
                result = "        Incorrect value returned in iCalendar for %s\n" % (node_path,)

        # Try to parse as JSON
        elif test == 'json':
            try:
                json.loads(node.text)
            except:
                result = "        Incorrect value returned in XML for %s\n" % (node_path,)
        return result


    @classmethod
    def matchNode(cls, root, xpath, parent_map=None, title=None):

        if title is None:
            title = xpath
        result = True
        resulttxt = ""

        # Find the first test in the xpath
        if '[' in xpath:
            actual_xpath, tests = xpath.split('[', 1)
        else:
            actual_xpath = xpath
            tests = None

        if parent_map is None:
            parent_map = dict((c, p) for p in root.getiterator() for c in p)

        # Handle parents
        if actual_xpath.startswith("../"):
            root = parent_map[root]
            actual_xpath = "./" + actual_xpath[3:]

        # Handle absolute root element and find all matching nodes
        r = re.search("(/?\{[^\}]+\}[^/]+|\.)(.*)", actual_xpath)
        if r.group(2):
            root_path = r.group(1)
            child_path = r.group(2)[1:]
            if root_path != "." and root.tag != root_path.lstrip("/"):
                resulttxt += "        Items not returned in XML for %s\n" % (title,)
                result = False
                return result, resulttxt
            nodes = root.findall(child_path)
        else:
            nodes = (root,)

        if len(nodes) == 0:
            resulttxt += "        Items not returned in XML for %s\n" % (title,)
            result = False
            return result, resulttxt


        if tests:
            # Split the tests into tests plus additional path
            pos = tests.find("]/")
            if pos != -1:
                node_tests = tests[:pos + 1]
                next_path = tests[pos + 1:]
            else:
                node_tests = tests
                next_path = None

            node_tests = [item[:-1] for item in node_tests.split('[')]
            for test in node_tests:
                for node in nodes:
                    testresult = cls.testNode(node, title, test)
                    if testresult is None:
                        if next_path:
                            next_result, testresult = cls.matchNode(node, next_path[1:], parent_map, title)
                            if next_result:
                                break
                        else:
                            break

                if testresult:
                    resulttxt += testresult
                    result = False
                    break

        return result, resulttxt


# Tests
if __name__ == '__main__':
    xmldata = """
<D:test xmlns:D="DAV:">
    <D:a>A</D:a>
    <D:b>
        <D:c>C</D:c>
        <D:d>D</D:d>
    </D:b>
    <D:b>
        <D:c>C</D:c>
        <D:d>F</D:d>
    </D:b>
</D:test>
"""

    node = ElementTree(file=StringIO.StringIO(xmldata)).getroot()

    assert Verifier.matchNode(node, "/{DAV:}test/{DAV:}b/{DAV:}c[=C]/../{DAV:}d[=D]")[0]
    assert not Verifier.matchNode(node, "/{DAV:}test/{DAV:}b/{DAV:}c[=C]/../{DAV:}d[=E]")[0]
