#!/usr/bin/env python
# coding=utf-8
#
##
# Copyright (c) 2006-2015 Apple Inc. All rights reserved.
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

from getpass import getpass
from plistlib import readPlistFromString
from plistlib import writePlist
from subprocess import Popen, PIPE
import getopt
import os
import sys
import traceback
import uuid
import xml.parsers.expat

"""
OpenDirectory.framework
"""

import objc as _objc

__bundle__ = _objc.initFrameworkWrapper(
    "OpenDirectory",
    frameworkIdentifier="com.apple.OpenDirectory",
    frameworkPath=_objc.pathForFramework(
        "/System/Library/Frameworks/OpenDirectory.framework"
    ),
    globals=globals()
)

# DS attributes we need
kDSStdRecordTypeUsers = "dsRecTypeStandard:Users"
kDSStdRecordTypeGroups = "dsRecTypeStandard:Groups"
kDSStdRecordTypePlaces = "dsRecTypeStandard:Places"
kDSStdRecordTypeResources = "dsRecTypeStandard:Resources"

kDS1AttrGeneratedUID = "dsAttrTypeStandard:GeneratedUID"
kDSNAttrRecordName = "dsAttrTypeStandard:RecordName"

eDSExact = 0x2001


sys_root = "/Applications/Server.app/Contents/ServerRoot"
os.environ["PATH"] = "%s/usr/bin:%s" % (sys_root, os.environ["PATH"])

diradmin_user = "admin"
diradmin_pswd = ""
directory_node = "/LDAPv3/127.0.0.1"
utility = sys_root + "/usr/sbin/calendarserver_manage_principals"
cmdutility = sys_root + "/usr/sbin/calendarserver_command_gateway"
configutility = sys_root + "/usr/sbin/calendarserver_config"

verbose = False
veryverbose = False

serverinfo_template = "scripts/server/serverinfo-template.xml"

details = {
    "caldav": {
        "serverinfo": "scripts/server/serverinfo-caldav.xml"
    },
}

base_dir = "../CalendarServer/"

number_of_users = 40
number_of_groups = 40
number_of_publics = 10
number_of_resources = 20
number_of_locations = 10

guids = {
    "testadmin"  : "",
    "apprentice" : "",
    "i18nuser"   : "",
}

for i in range(1, number_of_users + 1):
    guids["user%02d" % (i,)] = ""

for i in range(1, number_of_publics + 1):
    guids["public%02d" % (i,)] = ""

for i in range(1, number_of_groups + 1):
    guids["group%02d" % (i,)] = ""

for i in range(1, number_of_resources + 1):
    guids["resource%02d" % (i,)] = ""

for i in range(1, number_of_locations + 1):
    guids["location%02d" % (i,)] = ""

locations = {}
resources = {}

# List of users as a tuple: (<<name>>, <<pswd>>, <<repeat count>>)
adminattrs = {
    "dsAttrTypeStandard:RealName": "Super User",
    "dsAttrTypeStandard:FirstName": "Super",
    "dsAttrTypeStandard:LastName": "User",
    "dsAttrTypeStandard:EMailAddress": "testadmin@example.com",
}

apprenticeattrs = {
    "dsAttrTypeStandard:RealName": "Apprentice Super User",
    "dsAttrTypeStandard:FirstName": "Apprentice",
    "dsAttrTypeStandard:LastName": "Super User",
    "dsAttrTypeStandard:EMailAddress": "apprentice@example.com",
}

userattrs = {
    "dsAttrTypeStandard:RealName": "User %02d",
    "dsAttrTypeStandard:FirstName": "User",
    "dsAttrTypeStandard:LastName": "%02d",
    "dsAttrTypeStandard:EMailAddress": "user%02d@example.com",
}

publicattrs = {
    "dsAttrTypeStandard:RealName": "Public %02d",
    "dsAttrTypeStandard:FirstName": "Public",
    "dsAttrTypeStandard:LastName": "%02d",
    "dsAttrTypeStandard:EMailAddress": "public%02d@example.com",
    "dsAttrTypeStandard:Street": "%d Public Row",
    "dsAttrTypeStandard:City": "Exampleville",
    "dsAttrTypeStandard:State": "Testshire",
    "dsAttrTypeStandard:PostalCode": "RFC 4791",
    "dsAttrTypeStandard:Country": "AAA",
}

i18nattrs = {
    "dsAttrTypeStandard:RealName": u"まだ",
    "dsAttrTypeStandard:FirstName": u"ま",
    "dsAttrTypeStandard:LastName": u"だ",
    "dsAttrTypeStandard:EMailAddress": "i18nuser@example.com",
}

locationcreatecmd = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>command</key>
        <string>createLocation</string>
        <key>AutoScheduleMode</key>
        <string>acceptIfFreeDeclineIfBusy</string>
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
        <key>AutoScheduleMode</key>
        <string>acceptIfFreeDeclineIfBusy</string>
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
    "dsAttrTypeStandard:RealName": "Location %02d",
}

delegatedroomattrs = {
    "dsAttrTypeStandard:RealName": "Delegated Conference Room",
}

resourceattrs = {
    "dsAttrTypeStandard:RealName": "Resource %02d",
}

groupattrs = {
    "dsAttrTypeStandard:RealName": "Group %02d",
    "dsAttrTypeStandard:EMailAddress": "group%02d@example.com",
}

records = (
    (kDSStdRecordTypeUsers, "testadmin", "testadmin", adminattrs, 1),
    (kDSStdRecordTypeUsers, "apprentice", "apprentice", apprenticeattrs, 1),
    (kDSStdRecordTypeUsers, "i18nuser", "i18nuser", i18nattrs, 1),
    (kDSStdRecordTypeUsers, "user%02d", "user%02d", userattrs, None),
    (kDSStdRecordTypeUsers, "public%02d", "public%02d", publicattrs, number_of_publics),
    (kDSStdRecordTypePlaces, "location%02d", "location%02d", locationattrs, number_of_locations),
    (kDSStdRecordTypePlaces, "delegatedroom", "delegatedroom", delegatedroomattrs, 1),
    (kDSStdRecordTypeResources, "resource%02d", "resource%02d", resourceattrs, number_of_resources),
    (kDSStdRecordTypeGroups, "group%02d", "group%02d", groupattrs, number_of_groups),
)

def usage():
    print """Usage: odsetup [options] create|create-users|remove
Options:
    -h        Print this help and exit
    -n node   OpenDirectory node to target
    -u uid    OpenDirectory Admin user id
    -p pswd   OpenDirectory Admin user password
    -c users  number of user accounts to create (default: 10)
    -x        disable OD node checks
    -v        verbose logging
    -V        very verbose logging
"""



def cmd(args, input=None, raiseOnFail=True):

    if veryverbose:
        print "-----"
    if verbose:
        print args.replace(diradmin_pswd, "xxxx")
    if veryverbose and input:
        print input
        print "*****"
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



def checkDataSource(node):
    """
    Verify that the specified node is the only node this host is bound to.

    @param node: the node to verify
    @type node: L{str}
    """

    result = cmd("dscl localhost -list /LDAPv3")
    result = ["/LDAPv3/{}".format(subnode) for subnode in result[0].splitlines()]
    if len(result) > 1 or result[0] != node:
        print "Error: Host is bound to other directory nodes: {}".format(result)
        print "CalDAVTester will likely fail with other nodes present."
        print "Please remove all nodes except the one being used for odsetup."
        sys.exit(1)



class ODError(Exception):
    pass



class ODFamework(object):

    def __init__(self, nodeName, user, pswd):
        self.session = ODSession.defaultSession()
        self.node, error = ODNode.nodeWithSession_name_error_(self.session, nodeName, None)
        if error:
            print(error)
            raise ODError(error)

        _ignore_result, error = self.node.setCredentialsWithRecordType_recordName_password_error_(
            kDSStdRecordTypeUsers,
            user,
            pswd,
            None
        )
        if error:
            print("Unable to authenticate with directory %s: %s" % (nodeName, error))
            raise ODError(error)

        print("Successfully authenticated with directory %s" % (nodeName,))


    def lookupRecordName(self, recordType, name):
        query, error = ODQuery.queryWithNode_forRecordTypes_attribute_matchType_queryValues_returnAttributes_maximumResults_error_(
            self.node,
            recordType,
            kDSNAttrRecordName,
            eDSExact,
            name,
            [kDS1AttrGeneratedUID],
            0,
            None)
        if error:
            raise ODError(error)
        records, error = query.resultsAllowingPartial_error_(False, None)
        if error:
            raise ODError(error)

        if len(records) < 1:
            return None
        if len(records) > 1:
            raise ODError("Multiple records for '%s' were found" % (name,))

        return records[0]


    def createRecord(self, recordType, recordName, password, attrs):
        record, error = self.node.createRecordWithRecordType_name_attributes_error_(
            recordType,
            recordName,
            attrs,
            None)
        if error:
            print(error)
            raise ODError(error)
        if recordType == kDSStdRecordTypeUsers:
            _ignore_result, error = record.changePassword_toPassword_error_(None, password, None)
            if error:
                print(error)
                raise ODError(error)
        return record


    def recordDetails(self, record):
        details, error = record.recordDetailsForAttributes_error_(None, None)
        if error:
            print(error)
            raise ODError(error)
        return details



def readConfig():
    """
    Read useful information from calendarserver_config
    """

    args = [
        configutility,
        "ServerHostName",
        "ConfigRoot",
        "DocumentRoot",
        "HTTPPort",
        "SSLPort",
        "Authentication.Basic.Enabled",
        "Authentication.Digest.Enabled",
    ]
    currentConfig = {}
    output, _ignore_code = cmd(" ".join(args), input=None)
    for line in output.split("\n"):
        if line:
            key, value = line.split("=")
            currentConfig[key] = value
    try:
        basic_ok = currentConfig["Authentication.Basic.Enabled"]
    except KeyError:
        basic_ok = False
    try:
        digest_ok = currentConfig["Authentication.Digest.Enabled"]
    except KeyError:
        digest_ok = False
    if digest_ok:
        authtype = "digest"
    elif basic_ok:
        authtype = "basic"

    return (
        currentConfig["ServerHostName"],
        int(currentConfig["HTTPPort"]),
        int(currentConfig["SSLPort"]),
        authtype,
        currentConfig["DocumentRoot"],
        currentConfig["ConfigRoot"],
    )



def patchConfig(confroot, admin):
    """
    Patch the caldavd-user.plist file to make sure:
       * the proper admin principal is configured
       * iMIP is disabled
       * SACLs are disabled
       * EnableAnonymousReadRoot is enabled
       * WorkQueue timings are appropriate for testing (low delay)

    @param admin: admin principal-URL value
    @type admin: str
    """
    plist = {}
    plist["AdminPrincipals"] = [admin]

    # For testing do not send iMIP messages!
    plist["Scheduling"] = {
        "iMIP" : {
            "Enabled" : False,
        },
    }

    # No SACLs
    plist["EnableSACLs"] = False

    # Needed for CDT
    plist["EnableAnonymousReadRoot"] = True
    plist["EnableControlAPI"] = True
    if "Options" not in plist["Scheduling"]:
        plist["Scheduling"]["Options"] = dict()

    # Lower WorkQueue timings to reduce processing delay
    plist["Scheduling"]["Options"]["WorkQueues"] = {
        "Enabled" : True,
        "RequestDelaySeconds" : 0.1,
        "ReplyDelaySeconds" : 1,
        "AutoReplyDelaySeconds" : 0.1,
        "AttendeeRefreshBatchDelaySeconds" : 0.1,
        "AttendeeRefreshBatchIntervalSeconds" : 0.1,
    }
    plist["WorkQueue"] = {
        "failureRescheduleInterval": 1,
        "lockRescheduleInterval": 1,
    }

    writePlist(plist, confroot + "/caldavd-user.plist")



def buildServerinfo(serverinfo_default, hostname, nonsslport, sslport, authtype, docroot):

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
        ("$useradminguid:", guids["testadmin"]),
        ("$userapprenticeguid:", guids["apprentice"]),
        ("$i18nguid:", guids["i18nuser"]),
    ]

    for i in range(1, number_of_users + 1):
        subs.append(("$userguid%d:" % (i,), guids["user%02d" % (i,)]))
    for i in range(1, number_of_publics + 1):
        subs.append(("$publicuserguid%d:" % (i,), guids["public%02d" % (i,)]))
    for i in range(1, number_of_resources + 1):
        subs.append(("$resourceguid%d:" % (i,), guids["resource%02d" % (i,)]))
    for i in range(1, number_of_locations + 1):
        subs.append(("$locationguid%d:" % (i,), guids["location%02d" % (i,)]))
    for i in range(1, number_of_groups + 1):
        subs.append(("$groupguid%d:" % (i,), guids["group%02d" % (i,)]))

    subs_str = ""
    for x, y in subs:
        subs_str += subs_template % (x, y,)

    data = data.format(
        hostname=hostname,
        nonsslport=str(nonsslport),
        sslport=str(sslport),
        authtype=authtype,
        overrides=subs_str,
        DAV="{DAV:}",
    )

    fd = open(serverinfo_default, "w")
    try:
        fd.write(data)
    finally:
        fd.close()



def loadLists(path, records):
    if path == kDSStdRecordTypePlaces:
        result = cmd(cmdutility, locationlistcmd)
    elif path == kDSStdRecordTypeResources:
        result = cmd(cmdutility, resourcelistcmd)
    else:
        raise ValueError()

    try:
        plist = readPlistFromString(result[0])
    except xml.parsers.expat.ExpatError, e:
        print "Error (%s) parsing (%s)" % (e, result[0])
        raise

    for record in plist["result"]:
        records[record["RecordName"][0]] = record["GeneratedUID"]



def doToAccounts(odf, protocol, f, users_only=False):

    for record in records:
        if protocol == "carddav" and record[0] in (kDSStdRecordTypePlaces, kDSStdRecordTypeResources):
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
                f(odf, record[0], ruser)
        else:
            f(odf, record[0], record[1:])



def doGroupMemberships(odf):

    memberships = (
        ("group01", ("user01",), (),),
        ("group02", ("user06", "user07",), (),),
        ("group03", ("user08", "user09",), (),),
        ("group04", ("user10",), ("group02", "group03",),),
        ("group05", ("user20",), ("group06",),),
        ("group06", ("user21",), (),),
        ("group07", ("user22", "user23", "user24",), (),),
    )

    for groupname, users, nestedgroups in memberships:
        if verbose:
            print "Group membership: {}".format(groupname)

        # Get group record
        group = odf.lookupRecordName(kDSStdRecordTypeGroups, groupname)
        if group is not None:
            for user in users:
                member = odf.lookupRecordName(kDSStdRecordTypeUsers, user)
                if member is not None:
                    _ignore_result, error = group.addMemberRecord_error_(member, None)
                    if error:
                        raise ODError(error)
            for nested in nestedgroups:
                member = odf.lookupRecordName(kDSStdRecordTypeGroups, nested)
                if member is not None:
                    _ignore_result, error = group.addMemberRecord_error_(member, None)
                    if error:
                        raise ODError(error)



def createUser(odf, path, user):

    if verbose:
        print "Create user: {}/{}".format(path, user[0])

    if path in (kDSStdRecordTypeUsers, kDSStdRecordTypeGroups,):
        createUserViaDS(odf, path, user)
    elif protocol == "caldav":
        createUserViaGateway(path, user)



def createUserViaDS(odf, path, user):
    # Do dscl command line operations to create a calendar user

    # Only create if it does not exist
    record = odf.lookupRecordName(path, user[0])

    if record is None:
        # Create the user
        if kDS1AttrGeneratedUID in user[2]:
            user[2][kDS1AttrGeneratedUID] = str(uuid.uuid4()).upper()

        user = (user[0], user[1], dict([(k, [v],) for k, v in user[2].items()]),)
        record = odf.createRecord(path, user[0], user[1], user[2])
    else:
        if verbose:
            print "%s/%s already exists" % (path, user[0],)

    # Now read the guid for this record
    if user[0] in guids:
        record = odf.lookupRecordName(path, user[0])
        details = odf.recordDetails(record)
        guids[user[0]] = details[kDS1AttrGeneratedUID][0]



def createUserViaGateway(path, user):

    # Check for existing
    if path == kDSStdRecordTypePlaces:
        if user[0] in locations:
            guids[user[0]] = locations[user[0]]
            return
    elif path == kDSStdRecordTypeResources:
        if user[0] in resources:
            guids[user[0]] = resources[user[0]]
            return

    guid = str(uuid.uuid4()).upper()
    if user[0] in guids:
        guids[user[0]] = guid
    if path == kDSStdRecordTypePlaces:
        cmd(
            cmdutility,
            locationcreatecmd % {
                "guid": guid,
                "realname": user[2]["dsAttrTypeStandard:RealName"],
                "recordname": user[0]
            }
        )
    elif path == kDSStdRecordTypeResources:
        cmd(
            cmdutility,
            resourcecreatecmd % {
                "guid": guid,
                "realname": user[2]["dsAttrTypeStandard:RealName"],
                "recordname": user[0]
            }
        )
    else:
        raise ValueError()



def removeUser(odf, path, user):

    if verbose:
        print "Remove user: {}/{}".format(path, user[0])

    if path in (kDSStdRecordTypeUsers, kDSStdRecordTypeGroups,):
        removeUserViaDS(odf, path, user)
    else:
        removeUserViaGateway(path, user)



def removeUserViaDS(odf, path, user):
    # Do dscl command line operations to remove a calendar user

    record = odf.lookupRecordName(path, user[0])
    if record is not None:
        _ignore_result, error = record.deleteRecordAndReturnError_(None)
        if error:
            raise ODError(error)



def removeUserViaGateway(path, user):

    if path == kDSStdRecordTypePlaces:
        if user[0] not in locations:
            return
        guid = locations[user[0]]
        cmd(
            cmdutility,
            locationremovecmd % {"guid": guid, }
        )
    elif path == kDSStdRecordTypeResources:
        if user[0] not in resources:
            return
        guid = resources[user[0]]
        cmd(
            cmdutility,
            resourceremovecmd % {"guid": guid, }
        )
    else:
        raise ValueError()



def manageRecords(odf, path, user):
    """
    Set proxies and auto-schedule for locations and resources
    """

    # Do caldav_utility setup
    if path in (kDSStdRecordTypePlaces, kDSStdRecordTypeResources,):
        if path in (kDSStdRecordTypePlaces,):
            if user[0] == "delegatedroom":
                cmd("%s --add-write-proxy groups:group05 --add-read-proxy groups:group07 --set-auto-schedule-mode=none locations:%s" % (
                    utility,
                    user[0],
                ))
            else:
                cmd("%s --add-write-proxy users:user01 --set-auto-schedule-mode=automatic locations:%s" % (
                    utility,
                    user[0],
                ))
        else:
            # Default options for all resources
            cmd("%s --add-write-proxy users:user01 --add-read-proxy users:user03 --set-auto-schedule-mode=automatic resources:%s" % (
                utility,
                user[0],
            ))

            # Some resources have unique auto-schedule mode set
            automodes = {
                "resource05" : "none",
                "resource06" : "accept-always",
                "resource07" : "decline-always",
                "resource08" : "accept-if-free",
                "resource09" : "decline-if-busy",
                "resource10" : "automatic",
                "resource11" : "decline-always",
            }

            if user[0] in automodes:
                cmd("%s --set-auto-schedule-mode=%s resources:%s" % (
                    utility,
                    automodes[user[0]],
                    user[0],
                ))

            # Some resources have unique auto-accept-groups assigned
            autoAcceptGroups = {
                "resource11" : "group01",
            }
            if user[0] in autoAcceptGroups:
                cmd("%s --set-auto-accept-group=groups:%s resources:%s" % (
                    utility,
                    autoAcceptGroups[user[0]],
                    user[0],
                ))


if __name__ == "__main__":

    protocol = "caldav"
    serverinfo_default = details[protocol]["serverinfo"]
    node_check = True
    try:
        options, args = getopt.getopt(sys.argv[1:], "hn:p:u:f:c:vVx")

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
            elif option == "-c":
                number_of_users = int(value)
            elif option == "-v":
                verbose = True
            elif option == "-V":
                verbose = True
                veryverbose = True
            elif option == "-x":
                node_check = False
            else:
                print "Unrecognized option: %s" % (option,)
                usage()
                raise ValueError

        if not diradmin_pswd:
            diradmin_pswd = getpass("Directory Admin Password: ")

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

        odf = ODFamework(directory_node, diradmin_user, diradmin_pswd)

        if node_check:
            checkDataSource(directory_node)

        if args[0] == "create":
            # Read the caldavd.plist file and extract some information we will need.
            hostname, port, sslport, authtype, docroot, confroot = readConfig()

            # Now generate the OD accounts (caching guids as we go).
            if protocol == "caldav":
                loadLists(kDSStdRecordTypePlaces, locations)
                loadLists(kDSStdRecordTypeResources, resources)

            doToAccounts(odf, protocol, createUser)
            doGroupMemberships(odf)
            doToAccounts(odf, protocol, manageRecords)

            # Patch the caldavd.plist file with the testadmin user's guid-based principal-URL
            patchConfig(confroot, "/principals/__uids__/%s/" % (guids["testadmin"],))

            # Create an appropriate serverinfo.xml file from the template
            buildServerinfo(serverinfo_default, hostname, port, sslport, authtype, docroot)


        elif args[0] == "create-users":
            # Read the caldavd.plist file and extract some information we will need.
            hostname, port, sslport, authtype, docroot, confroot = readConfig()

            # Now generate the OD accounts (caching guids as we go).
            if protocol == "caldav":
                loadLists(kDSStdRecordTypePlaces, locations)
                loadLists(kDSStdRecordTypeResources, resources)

            doToAccounts(odf, protocol, createUser, users_only=True)

            # Create an appropriate serverinfo.xml file from the template
            buildServerinfo(serverinfo_default, hostname, port, sslport, authtype, docroot)

        elif args[0] == "remove":
            if protocol == "caldav":
                loadLists(kDSStdRecordTypePlaces, locations)
                loadLists(kDSStdRecordTypeResources, resources)
            doToAccounts(odf, protocol, removeUser)

    except Exception, e:
        traceback.print_exc()
        sys.exit(1)
