##
# Copyright (c) 2007 Apple Inc. All rights reserved.
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
XML processing utilities.
"""

import src.xmlDefs

def readStringElementList(node, ename):
    
    results = []
    for child in node._get_childNodes():
        if child._get_localName() == ename:
            results.append(child.firstChild.data.decode("utf-8"))
    return results

def getYesNoAttributeValue(node, attr):
    return node.getAttribute(attr) != src.xmlDefs.ATTR_VALUE_NO

def getDefaultAttributeValue(node, attr, default):
    result = node.getAttribute(attr)
    if result:
        return result
    else:
        return default

def readOneStringElement(node, ename):
    
    for child in node._get_childNodes():
        if child._get_localName() == ename:
            return child.firstChild.data.decode("utf-8")
    return ""
