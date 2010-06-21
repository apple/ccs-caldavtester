#!/usr/bin/env python
#
##
# Copyright (c) 2006-2009 Apple Inc. All rights reserved.
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
#
# Creates some test accounts on an OpenDirectory server for use with CalDAVTester
#

from plistlib import readPlist, readPlistFromString
from plistlib import writePlist
import getopt
import os
import sys
import uuid
from getpass import getpass
from subprocess import Popen, PIPE
import xml.parsers.expat

diradmin_user    = "admin"
diradmin_pswd    = ""
directory_node   = "/LDAPv3/127.0.0.1"
utility          = "/usr/sbin/calendarserver_manage_principals"
cmdutility       = "/usr/sbin/calendarserver_command_gateway"

verbose = False
veryverbose = False

serverinfo_template = "scripts/server/serverinfo-template.xml"

details = {
    "caldav": {
        "config": "/etc/caldavd/caldavd.plist",
        "serverinfo": "scripts/server/serverinfo-caldav.xml"
    },
    "carddav": {
        "config": "/etc/carddavd/carddavd.plist",
        "serverinfo": "scripts/server/serverinfo-carddav.xml"
    }
}

base_dir = "../CalendarServer/"

number_of_users = 40

guids = {
    "testadmin"  : "",
    "apprentice" : "",
}

for i in range(1, number_of_users + 1):
    guids["user%02d" % (i,)] = ""
    guids["public%02d" % (i,)] = ""
    guids["resource%02d" % (i,)] = ""
    guids["location%02d" % (i,)] = ""

for i in range(1, 5):
    guids["group%02d" % (i,)] = ""

locations = {}
resources = {}

# List of users as a tuple: (<<name>>, <<pswd>>, <<repeat count>>)
adminattrs = {
    "dsAttrTypeStandard:RealName":        "Super User",
    "dsAttrTypeStandard:FirstName":       "Super",
    "dsAttrTypeStandard:LastName":        "User",
    "dsAttrTypeStandard:EMailAddress":    "testadmin@example.com",
}

apprenticeattrs = {
    "dsAttrTypeStandard:RealName":        "Apprentice Super User",
    "dsAttrTypeStandard:FirstName":       "Apprentice",
    "dsAttrTypeStandard:LastName":        "Super User",
    "dsAttrTypeStandard:EMailAddress":    "apprentice@example.com",
}

userattrs = {
    "dsAttrTypeStandard:RealName":        "User %02d",
    "dsAttrTypeStandard:FirstName":       "User",
    "dsAttrTypeStandard:LastName":        "%02d",
    "dsAttrTypeStandard:EMailAddress":    "user%02d@example.com",
}

publicattrs = {
    "dsAttrTypeStandard:RealName":        "Public %02d",
    "dsAttrTypeStandard:FirstName":       "Public",
    "dsAttrTypeStandard:LastName":        "%02d",
    "dsAttrTypeStandard:EMailAddress":    "public%02d@example.com",
    "dsAttrTypeStandard:Street":          "%d Public Row",
    "dsAttrTypeStandard:City":            "Exampleville",
    "dsAttrTypeStandard:State":           "Testshire",
    "dsAttrTypeStandard:PostalCode":      "RFC 4791",
    "dsAttrTypeStandard:Country":         "AAA",
}

locationcreatecmd = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>command</key>
        <string>createLocation</string>
        <key>AutoSchedule</key>
        <true/>
        <key>GeneratedUID</key>
        <string>%(guid)s</string>
        <key>RealName</key>
        <string>%(realname)s</string>
        <key>RecordName</key>
        <array>
                <string>%(recordname)s</string>
        </array>
</dict>
</plist>
"""

locationremovecmd = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>command</key>
        <string>deleteLocation</string>
        <key>GeneratedUID</key>
        <string>%(guid)s</string>
</dict>
</plist>
"""

locationlistcmd = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>command</key>
        <string>getLocationList</string>
</dict>
</plist>
"""

resourcecreatecmd = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>command</key>
        <string>createResource</string>
        <key>AutoSchedule</key>
        <true/>
        <key>GeneratedUID</key>
        <string>%(guid)s</string>
        <key>RealName</key>
        <string>%(realname)s</string>
        <key>Type</key>
        <string>Printer</string>
        <key>RecordName</key>
        <array>
                <string>%(recordname)s</string>
        </array>
        <key>Comment</key>
        <string>Test Comment</string>
</dict>
</plist>
"""

resourceremovecmd = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>command</key>
        <string>deleteResource</string>
        <key>GeneratedUID</key>
        <string>%(guid)s</string>
</dict>
</plist>
"""

resourcelistcmd = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>command</key>
        <string>getResourceList</string>
</dict>
</plist>
"""

locationattrs = {
    "dsAttrTypeStandard:RealName":        "Room %02d",
}

resourceattrs = {
    "dsAttrTypeStandard:RealName":        "Resource %02d",
}

groupattrs = {
        "dsAttrTypeStandard:RealName":        "Group %02d",
}

records = (
    ("/Users", "testadmin", "testadmin", adminattrs, 1),
    ("/Users", "apprentice", "apprentice", apprenticeattrs, 1),
    ("/Users", "user%02d", "user%02d", userattrs, None),
    ("/Users", "public%02d", "public%02d", publicattrs, 10),
    ("/Places", "location%02d", "location%02d", locationattrs, 10),
    ("/Resources", "resource%02d", "resource%02d", resourceattrs, 10),
    ("/Groups", "group%02d", "group%02d", groupattrs, 4),
)

def usage():
    print """Usage: odsteup [options] create|create-users|remove
Options:
    -h        Print this help and exit
    -n node   OpenDirectory node to target
    -u uid    OpenDirectory Admin user id
    -p pswd   OpenDirectory Admin user password
    -f file   .plist config file used by the server
    -c users  number of user accounts to create (default: 10)
    -v        verbose logging
    -V        very verbose logging
    --caldav  testing CalDAV server
    --carddav testing CardDAV server
"""

def cmd(args, input=None, raiseOnFail=True):
    
    if veryverbose:
        print "-----"
    if verbose:
        print args
    if input:
        p = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True)
        result = p.communicate(input)
    else:
        p = Popen(args, stdout=PIPE, stderr=PIPE, shell=True)
        result = p.communicate()

    if veryverbose:
        print "Output: %s" % (result[0],)
        print "Code: %s" % (p.returncode,)
    if raiseOnFail and p.returncode:
        raise RuntimeError(result[1])
    return result[0], p.returncode

def readConfig(config):
    """
    Read useful information from the server's caldavd.plist file.

    @param config: file path to caldavd.plist
    @type config: str
    """

    # SudoersFile was removed from the default caldavd.plist. Cope.
    plist = readPlist(config)
    try:
        plist["SudoersFile"]
    except KeyError:
        # add SudoersFile entry to caldavd.plist
        plist["SudoersFile"] = "/etc/caldavd/sudoers.plist"
        writePlist(plist,config)

    try:
        sudoerspl = readPlist('/etc/caldavd/sudoers.plist')
    except IOError:
        # create a new sudoers.plist with empty 'users' array
        sudoerspl = {'users': []}
        writePlist(sudoerspl,'/etc/caldavd/sudoers.plist')

    plist = readPlist(config)
    hostname = plist["ServerHostName"]

    serverroot = plist["ServerRoot"]
    docroot = plist["DocumentRoot"]
    docroot = os.path.join(serverroot, docroot) if docroot and docroot[0] not in ('/', '.',) else docroot

    sudoers = plist["SudoersFile"]

    port = plist["HTTPPort"]

    try:
        basic_ok = plist["Authentication"]["Basic"]["Enabled"]
    except KeyError:
        pass
    try:
        digest_ok = plist["Authentication"]["Digest"]["Enabled"]
    except KeyError:
        pass
    if basic_ok:
        authtype = "basic"
    elif digest_ok:
        authtype = "digest"
    
    if not hostname:
        hostname = "localhost"
    if docroot[0] != "/":
        docroot = base_dir + docroot
    if sudoers[0] != "/":
        sudoers = base_dir + sudoers

    return hostname, port, authtype, docroot, sudoers

def patchConfig(config, admin):
    """
    Patch the caldavd.plist file to make sure the proper admin principal is configured.

    @param config: file path to caldavd.plist
    @type config: str
    @param admin: admin principal-URL value
    @type admin: str
    """
    plist = readPlist(config)

    admins = plist["AdminPrincipals"]
    admins[:] = [admin]

    # Only concern ourselves with the OD records we care about
    plist["DirectoryService"]["params"]["node"] = "/LDAPv3/127.0.0.1"

    # For testing do not send iMIP messages!
    plist["Scheduling"]["iMIP"]["Enabled"] = False

    # No SACLs
    plist["EnableSACLs"] = False

    writePlist(plist, config)

def patchSudoers(sudoers):
    """
    Patch the sudoers.plist file to add the superuser we need to test proxy authentication.

    @param sudoers: file path of sudoers file
    @type sudoers: str
    """
    plist = readPlist(sudoers)
    users = plist["users"]
    for user in users:
        if user["username"] == "superuser" and user["password"] == "superuser":
            break
    else:
        users.append({"username":"superuser", "password": "superuser"})
        writePlist(plist, sudoers)

def buildServerinfo(serverinfo_default, hostname, port, authtype, docroot):
    
    # Read in the serverinfo-template.xml file
    fd = open(serverinfo_template, "r")
    try:
        data = fd.read()
    finally:
        fd.close()

    subs_template = """
        <substitution>
            <key>%s</key>
            <value>%s</value>
        </substitution>
"""

    subs = [
        ("$useradminguid:",      guids["testadmin"]),
        ("$userapprenticeguid:", guids["apprentice"]),
        ("$groupguid1:",         guids["group01"]),
    ]
    
    for i in range(1, number_of_users + 1):
        subs.append(("$userguid%d:" % (i,), guids["user%02d" % (i,)]))
    for i in range(1, 11):
        subs.append(("$publicuserguid%d:" % (i,), guids["public%02d" % (i,)]))
    for i in range(1, 11):
        subs.append(("$resourceguid%d:" % (i,), guids["resource%02d" % (i,)]))
    for i in range(1, 11):
        subs.append(("$locationguid%d:" % (i,), guids["location%02d" % (i,)]))
    for i in range(1, 5):
        subs.append(("$groupguid%d:" % (i,), guids["group%02d" % (i,)]))
    
    subs_str = ""
    for x, y in subs:
        subs_str += subs_template % (x, y,)

    data = data % {
        "hostname"       : hostname,
        "port"           : str(port),
        "authtype"       : authtype,
        "overrides"      : subs_str,
    }
    
    fd = open(serverinfo_default, "w")
    try:
        fd.write(data)
    finally:
        fd.close()


def addLargeCalendars(hostname, docroot):
    largeCalendarUser = "user09"
    calendars = ("calendar.10", "calendar.100", "calendar.1000",)
    largeGuid = guids[largeCalendarUser]
    path = os.path.join(
        docroot,
        "calendars",
        "__uids__",
        largeGuid[0:2],
        largeGuid[2:4],
        largeGuid,
    )

    result = cmd("curl --digest -u %s:%s 'http://%s:8008/calendars/users/%s/'" % (
        largeCalendarUser,
        largeCalendarUser,
        hostname,
        largeCalendarUser,
    ), raiseOnFail=False)

    if result[1] == 0:
        for calendar in calendars:
            cmd("tar -C %s -zx -f data/%s.tgz" % (path, calendar,))
            cmd("chown -R calendar:calendar %s" % (os.path.join(path, calendar) ,))

def loadLists(config, path, records):
    if path == "/Places":
        result = cmd(
            "%s -f %s" % (cmdutility, config,),
            locationlistcmd,
        )
    elif path == "/Resources":
        result = cmd(
            "%s -f %s" % (cmdutility, config,),
            resourcelistcmd
        )
    else:
        raise ValueError()

    try:
        plist = readPlistFromString(result[0])
    except xml.parsers.expat.ExpatError, e:
        print "Error (%s) parsing (%s)" % (e, result[0])
        raise

    for record in plist["result"]:
        records[record["RecordName"][0]] = record["GeneratedUID"] 

def doToAccounts(config, protocol, f, users_only=False):
    
    for record in records:
        if protocol == "carddav" and record[0] in ("/Places", "/Resources"):
            continue
        if record[4] is None:
            count = number_of_users
        elif users_only:
            continue
        else:
            count = record[4]
        if count > 1:
            for ctr in range(1, count + 1):
                attrs = {}
                for key, value in record[3].iteritems():
                    if value.find("%02d") != -1:
                        value = value % (ctr,)
                    attrs[key] = value
                ruser = (record[1] % (ctr,), record[2] % (ctr,), attrs, 1)
                f(config, record[0], ruser)
        else:
            f(config, record[0], record[1:])

def doGroupMemberships():
    
    memberships = (
        ("group01", ("user01",), (),),
        ("group02", ("user06", "user07",), (),),
        ("group03", ("user08", "user09",), (),),
        ("group04", ("user10",), ("group02", "group03",),),
    )
    
    for groupname, users, nestedgroups in memberships:
        
        memberGUIDs = [guids[user] for user in users]
        nestedGUIDs = [guids[group] for group in nestedgroups]
        
        cmd("dscl -u %s -P %s %s -append /Groups/%s \"dsAttrTypeStandard:GroupMembers\"%s" % (diradmin_user, diradmin_pswd, directory_node, groupname, "".join([" \"%s\"" % (guid,) for guid in memberGUIDs])), raiseOnFail=False)
        cmd("dscl -u %s -P %s %s -append /Groups/%s \"dsAttrTypeStandard:NestedGroups\"%s" % (diradmin_user, diradmin_pswd, directory_node, groupname, "".join([" \"%s\"" % (guid,) for guid in nestedGUIDs])), raiseOnFail=False)

def createUser(config, path, user):
    
    if path in ("/Users", "/Groups",):
        createUserViaDS(config, path, user)
    elif protocol == "caldav":
        createUserViaGateway(config, path, user)
        
    # Do caldav_utility setup
    if path in ("/Places", "/Resources",):
        if path in ("/Places",):
            cmd("%s --add-write-proxy users:user01 --set-auto-schedule=true locations:%s" % (
                utility,
                user[0],
            ))
        else:
            cmd("%s --add-write-proxy users:user01 --add-read-proxy users:user03 --set-auto-schedule=true resources:%s" % (
                utility,
                user[0],
            ))

def createUserViaDS(config, path, user):
    # Do dscl command line operations to create a calendar user
    
    # Only create if it does not exist
    if cmd("dscl %s -list %s/%s" % (directory_node, path, user[0]), raiseOnFail=False)[1] != 0:
        # Create the user
        cmd("dscl -u %s -P %s %s -create %s/%s" % (diradmin_user, diradmin_pswd, directory_node, path, user[0]))
        
        # Set the password (only for /Users)
        if path == "/Users":
            cmd("dscl -u %s -P %s %s -passwd %s/%s %s" % (diradmin_user, diradmin_pswd, directory_node, path, user[0], user[1]))
    
        # Other attributes
        for key, value in user[2].iteritems():
            if key == "dsAttrTypeStandard:GeneratedUID":
                value = uuid.uuid4()
            cmd("dscl -u %s -P %s %s -create %s/%s \"%s\" \"%s\"" % (diradmin_user, diradmin_pswd, directory_node, path, user[0], key, value))
    else:
        print "%s/%s already exists" % (path, user[0],)

    # Now read the guid for this record
    if guids.has_key(user[0]):
        result = cmd("dscl %s -read %s/%s GeneratedUID"  % (directory_node, path, user[0]))
        guid = result[0].split()[1]
        guids[user[0]] = guid

def createUserViaGateway(config, path, user):
    
    # Check for existing
    if path == "/Places":
        if user[0] in locations:
            guids[user[0]] = locations[user[0]]
            return
    elif path == "/Resources":
        if user[0] in resources:
            guids[user[0]] = resources[user[0]]
            return
    
    guid = uuid.uuid4()
    if guids.has_key(user[0]):
        guids[user[0]] = guid
    if path == "/Places":
        cmd(
            "%s -f %s" % (cmdutility, config,),
            locationcreatecmd % {
                "guid":guid,
                "realname":user[2]["dsAttrTypeStandard:RealName"],
                "recordname":user[0]
            }
        )
    elif path == "/Resources":
        cmd(
            "%s -f %s" % (cmdutility, config,),
            resourcecreatecmd % {
                "guid":guid,
                "realname":user[2]["dsAttrTypeStandard:RealName"],
                "recordname":user[0]
            }
        )
    else:
        raise ValueError()
    
def removeUser(config, path, user):
    
    if path in ("/Users", "/Groups",):
        removeUserViaDS(config, path, user)
    else:
        removeUserViaGateway(config, path, user)

def removeUserViaDS(config, path, user):
    # Do dscl command line operations to create a calendar user
    
    # Create the user
    cmd("dscl -u %s -P %s %s -delete %s/%s" % (diradmin_user, diradmin_pswd, directory_node, path, user[0]), raiseOnFail=False)

def removeUserViaGateway(config, path, user):
    
    if path == "/Places":
        if user[0] not in locations:
            return
        guid = locations[user[0]]
        cmd(
            "%s -f %s" % (cmdutility, config,),
            locationremovecmd % {"guid":guid,}
        )
    elif path == "/Resources":
        if user[0] not in resources:
            return
        guid = resources[user[0]]
        cmd(
            "%s -f %s" % (cmdutility, config,),
            resourceremovecmd % {"guid":guid,}
        )
    else:
        raise ValueError()

if __name__ == "__main__":

    config = None
    protocol = None
    serverinfo_default = None
    try:
        options, args = getopt.getopt(sys.argv[1:], "hn:p:u:f:c:vV", ["carddav", "caldav", "old"])

        for option, value in options:
            if option == "-h":
                usage()
                sys.exit(0)
            elif option == "-n":
                directory_node = value
            elif option == "-u":
                diradmin_user = value
            elif option == "-p":
                diradmin_pswd = value
            elif option == "-f":
                config = value
            elif option == "-c":
                number_of_users = int(value)
            elif option == "-v":
                verbose = True
            elif option == "-V":
                verbose = True
                veryverbose = True
            elif option == "--carddav":
                protocol = "carddav"
            elif option == "--caldav":
                protocol = "caldav"
            else:
                print "Unrecognized option: %s" % (option,)
                usage()
                raise ValueError

        if not protocol:
            print "One of --carddav or --caldav MUST be specified"
            usage()
            raise ValueError
        else:
            if not config:
                config = details[protocol]["config"]
                serverinfo_default = details[protocol]["serverinfo"]
            
        if not diradmin_pswd:
            diradmin_pswd = getpass("Password: ")

        # Process arguments
        if len(args) == 0:
            print "No arguments given. One of 'create' or 'remove' must be present."
            usage()
            raise ValueError
        elif len(args) > 1:
            print "Too many arguments given. Only one of 'create' or 'remove' must be present."
            usage()
            raise ValueError
        elif args[0] not in ("create", "create-users", "remove"):
            print "Wrong arguments given: %s" % (args[0],)
            usage()
            raise ValueError
        
        if args[0] == "create":
            # Read the caldavd.plist file and extract some information we will need.
            hostname, port, authtype, docroot, sudoers = readConfig(config)
            
            # Patch the sudoers file for the superuser principal.
            patchSudoers(sudoers)
    
            # Now generate the OD accounts (caching guids as we go).
            if protocol == "caldav":
                loadLists(config, "/Places", locations)
                loadLists(config, "/Resources", resources)

            doToAccounts(config, protocol, createUser)
            doGroupMemberships()
            
            # Patch the caldavd.plist file with the testadmin user's guid-based principal-URL
            patchConfig(config, "/principals/__uids__/%s/" % (guids["testadmin"],))
            
            # Create an appropriate serverinfo.xml file from the template
            buildServerinfo(serverinfo_default, hostname, port, authtype, docroot)

            # Add large calendars to user account
            if protocol == "caldav":
                addLargeCalendars(hostname, docroot)

        elif args[0] == "create-users":
            # Read the caldavd.plist file and extract some information we will need.
            hostname, port, authtype, docroot, sudoers = readConfig(config)
            
            # Now generate the OD accounts (caching guids as we go).
            if protocol == "caldav":
                loadLists(config, "/Places", locations)
                loadLists(config, "/Resources", resources)

            doToAccounts(config, protocol, createUser, users_only=True)
            
            # Create an appropriate serverinfo.xml file from the template
            buildServerinfo(serverinfo_default, hostname, port, authtype, docroot)

        elif args[0] == "remove":
            if protocol == "caldav":
                loadLists(config, "/Places", locations)
                loadLists(config, "/Resources", resources)
            doToAccounts(config, protocol, removeUser)
            
    except Exception, e:
        sys.exit(str(e))
