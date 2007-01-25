#!/usr/bin/env python
#
##
# Copyright (c) 2006-2007 Apple Inc. All rights reserved.
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
#
# Creates some test accounts on an OpenDirectory server for use with CalDAVTester
#

from distutils.util import get_platform
import os
import subprocess
import sys

cwd = os.getcwd()
top = cwd[:cwd.rfind("/")]
add_paths = []
svn = "/usr/bin/svn"

packages = [
    ("vobject", "vobject/src", "http://svn.osafoundation.org/vobject/branches/users/cdaboo/vavailability-173", "178"),
    ("xattr", "xattr/build/lib.%s" % (get_platform(),), "http://svn.red-bean.com/bob/xattr/releases/xattr-0.4", "992"),
]

def getOtherPackages():
    for package in packages:
        ppath = "%s/%s" % (top, package[0],)
        if not os.path.exists(ppath):
            print "%s package is not present." % (package[0],)
            os.system("%s checkout -r %s %s@%s %s" % (svn, package[3], package[2], package[3], ppath,))
        else:
            print "%s package is present." % (package[0],)
            fd = os.popen("%s info ../%s --xml" % (svn, package[0],))
            line = fd.read()
            wc_url = line[line.find("<url>") + 5:line.find("</url>")]
            if wc_url != package[2]:
                print "Current working copy (%s) is from the wrong URI: %s != %s, switching..." % (ppath, wc_url, package[2],)
                os.system("%s switch -r %s %s %s" % (svn, package[3], package[2], ppath,))
            else:
                rev = line[line.find("revision=\"") + 10:]
                rev = rev[:rev.find("\"")]
                if rev != package[3]:
                    print "Updating %s..." % (package[0],)
                    os.system("%s update -r %s %s" % (svn, package[3], ppath,))

        add_paths.append("%s/%s" % (top, package[1],))

def runIt():
    pythonpath= ":".join(add_paths)
    subprocess.Popen(["./testcaldav.py", "availability.xml"], env={"PYTHONPATH":pythonpath}).wait()

if __name__ == "__main__":

    try:
        getOtherPackages()
        runIt()
    except Exception, e:
        sys.exit(str(e))