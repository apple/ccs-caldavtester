##
# Copyright (c) 2015 Apple Inc. All rights reserved.
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

def processHrefSubstitutions(hrefs, prefix):
    """
    Process the list of hrefs by prepending the supplied prefix. If the href is a
    list of hrefs, then prefix each item in the list and expand into the results. The
    empty string is represented by a single "-" in an href list.

    @param hrefs: list of URIs to process
    @type hrefs: L{list} of L{str}
    @param prefix: prefix to apply to each URI
    @type prefix: L{str}

    @return: resulting list of URIs
    @rtype: L{list} of L{str}
    """

    results = []
    for href in hrefs:
        if href.startswith("["):
            children = href[1:-1].split(",")
            results.extend([(prefix + (i if i != "-" else "")).rstrip("/") for i in children if i])
        else:
            results.append((prefix + href).rstrip("/"))

    return results
