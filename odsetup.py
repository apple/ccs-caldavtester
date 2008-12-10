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
##
#
# Creates some test accounts on an OpenDirectory server for use with CalDAVTester
#

from plistlib import readPlist
from plistlib import readPlistFromString
from plistlib import writePlist
import commands
import getopt
import os
import sys
import uuid

diradmin_user    = "admin"
diradmin_pswd    = "admin"
directory_node   = "/LDAPv3/127.0.0.1"
config           = "/etc/caldavd/caldavd.plist"
service_locator  = "Bogus"
old_style        = False

serverinfo_default = "scripts/server/serverinfo.xml"
serverinfo_template = "scripts/server/serverinfo-template.xml"
serverinfo_template_old = "scripts/server/serverinfo-template-old.xml"

base_dir = "../CalendarServer/"

number_of_users = 5

guids = {
    "testadmin": "",
    "user01":    "",
    "user02":    "",
    "user03":    "",
    "resource01":"",
}

# List of users as a tuple: (<<name>>, <<pswd>>, <<ServicesLocator value>, <<repeat count>>)
adminattrs = {
    "dsAttrTypeStandard:RealName":        "Test Admin",
    "dsAttrTypeStandard:EMailAddress":    "testadmin@example.com",
    "dsAttrTypeStandard:ServicesLocator": "Bogus"
}

userattrs = {
    "dsAttrTypeStandard:RealName":        "User %02d",
    "dsAttrTypeStandard:EMailAddress":    "user%02d@example.com",
    "dsAttrTypeStandard:ServicesLocator": "Bogus"
}

publicattrs = {
    "dsAttrTypeStandard:RealName":        "Public %02d",
    "dsAttrTypeStandard:EMailAddress":    "public%02d@example.com",
    "dsAttrTypeStandard:ServicesLocator": "Bogus"
}

locationattrs = {
    "dsAttrTypeStandard:GeneratedUID":    "Bogus",
    "dsAttrTypeStandard:RealName":        "Room %02d",
    "dsAttrTypeStandard:ServicesLocator": "Bogus",
    "dsAttrTypeStandard:ResourceType":    "1",
    "dsAttrTypeStandard:ResourceInfo":    """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.WhitePagesFramework</key>
    <dict>
        <key>AutoAcceptsInvitation</key>
        <true/>
        <key>CalendaringDelegate</key>
        <string>%(guid)s</string>
        <key>Label</key>
        <string>Room</string>
    </dict>
</dict>
</plist>""".replace("\n", "").replace('"', '\\"')
}

resourceattrs = {
    "dsAttrTypeStandard:GeneratedUID":    "Bogus",
    "dsAttrTypeStandard:RealName":        "Resource %02d",
    "dsAttrTypeStandard:ServicesLocator": "Bogus",
    "dsAttrTypeStandard:ResourceType":    "0",
    "dsAttrTypeStandard:ResourceInfo":    """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.WhitePagesFramework</key>
    <dict>
        <key>AutoAcceptsInvitation</key>
        <true/>
        <key>CalendaringDelegate</key>
        <string>%(guid)s</string>
        <key>Label</key>
        <string>Printer</string>
    </dict>
</dict>
</plist>""".replace("\n", "").replace('"', '\\"')
}

groupattrs = {
    "dsAttrTypeStandard:RealName":        "Group 01",
    "dsAttrTypeStandard:EMailAddress":    "group01@example.com",
    "dsAttrTypeStandard:ServicesLocator": "Bogus"
}

records = (
    ("/Users", "testadmin", "testadmin", adminattrs, 1),
    ("/Users", "user%02d", "user%02d", userattrs, None),
    ("/Users", "public%02d", "public%02d", publicattrs, 10),
    ("/Places", "location%02d", "location%02d", locationattrs, 10),
    ("/Resources", "resource%02d", "resource%02d", resourceattrs, 10),
    ("/Groups", "group01", "group01", groupattrs, 1),
)

def usage():
    print """Usage: odsteup [options] create|create-users|remove
Options:
    -h       Print this help and exit
    -n node  OpenDirectory node to target
    -u uid   OpenDirectory Admin user id
    -p pswd  OpenDirectory Admin user password
    -f file  caldavd.plist config file used by the server
    -c users number of user accounts to create (default: 5)
    --old    use old-style directory/principal-URL schema
"""

def readConfig(config):
    """
    Read useful information from the server's caldavd.plist file.

    @param config: file path to caldavd.plist
    @type config: str
    """
    plist = readPlist(config)
    hostname = plist["ServerHostName"]
    docroot = plist["DocumentRoot"]
    sudoers = plist["SudoersFile"]
    
    if docroot[0] != "/":
        docroot = base_dir + docroot
    if sudoers[0] != "/":
        sudoers = base_dir + sudoers

    return hostname, docroot, sudoers

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

def buildServerinfo(hostname, docroot):
    
    # Read in the serverinfo-template.xml file
    if old_style:
        fd = open(serverinfo_template_old, "r")
    else:
        fd = open(serverinfo_template, "r")
    try:
        data = fd.read()
    finally:
        fd.close()

    data = data % {
        "hostname"       : hostname,
        "docroot"        : docroot,
        "testadmin_guid" : guids["testadmin"],
        "user01_guid"    : guids["user01"],
        "user02_guid"    : guids["user02"],
        "user03_guid"    : guids["user03"],
        "resource01_guid": guids["resource01"],
    }
    
    fd = open(serverinfo_default, "w")
    try:
        fd.write(data)
    finally:
        fd.close()


def addLargeCalendars(hostname, docroot):
    calendars = ("calendar.10", "calendar.100", "calendar.1000",)
    path = os.path.join(docroot, "calendars/users/user01")    

    cmd = "curl --digest -u user01:user01 'http://%s:8008/calendars/users/user01/'" % (hostname,)
    commands.getoutput(cmd)

    for calendar in calendars:
        cmd = "tar -C %s -zx -f data/%s.tgz" % (path, calendar,)
        commands.getoutput(cmd)
        cpath = os.path.join(path, calendar)    
        cmd = "chown -R calendar:calendar %s" % (cpath,)
        commands.getoutput(cmd)
    
def doToAccounts(f, users_only=False):
    for record in records:
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
                f(record[0], ruser)
        else:
            f(record[0], record[1:])

def createUser(path, user):
    # Do dscl command line operations to create a calendar user
    
    if old_style and path == "/Places":
        path = "/Resources"

    # Only create if it does not exist
    cmd = "dscl -u %s -P %s %s -list %s/%s" % (diradmin_user, diradmin_pswd, directory_node, path, user[0])
    if commands.getstatusoutput(cmd)[0] != 0:
        # Create the user
        cmd = "dscl -u %s -P %s %s -create %s/%s" % (diradmin_user, diradmin_pswd, directory_node, path, user[0])
        print cmd
        commands.getoutput(cmd)
        
        # Set the password (only for /Users)
        if path == "/Users":
            cmd = "dscl -u %s -P %s %s -passwd %s/%s %s" % (diradmin_user, diradmin_pswd, directory_node, path, user[0], user[1])
            print cmd
            commands.getoutput(cmd)
    
        # Other attributes
        for key, value in user[2].iteritems():
            if key == "dsAttrTypeStandard:GeneratedUID":
                value = uuid.uuid4()
            elif key == "dsAttrTypeStandard:ServicesLocator":
                value = service_locator
            elif key == "dsAttrTypeStandard:ResourceInfo":
                value = value % {"guid":guids["user01"]}
            cmd = "dscl -u %s -P %s %s -create %s/%s \"%s\" \"%s\"" % (diradmin_user, diradmin_pswd, directory_node, path, user[0], key, value)
            print cmd
            commands.getoutput(cmd)
    else:
        print "%s/%s already exists" % (path, user[0],)

    # Now read the guid for this record
    if guids.has_key(user[0]):
        cmd = "dscl -u %s -P %s %s -read %s/%s GeneratedUID"  % (diradmin_user, diradmin_pswd, directory_node, path, user[0])
        result = commands.getoutput(cmd)
        guid = result.split()[1]
        guids[user[0]] = guid

def removeUser(path, user):
    # Do dscl command line operations to create a calendar user
    
    # Create the user
    cmd = "dscl -u %s -P %s %s -delete %s/%s" % (diradmin_user, diradmin_pswd, directory_node, path, user[0])
    print cmd
    commands.getoutput(cmd)

if __name__ == "__main__":

    try:
        options, args = getopt.getopt(sys.argv[1:], "hn:p:u:f:c:", ["old"])

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
            elif option == "--old":
                old_style = True
            else:
                print "Unrecognized option: %s" % (option,)
                usage()
                raise ValueError

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
            hostname, docroot, sudoers = readConfig(config)
            
            # Patch the sudoers file for the superuser principal.
            patchSudoers(sudoers)
    
            # Now generate the OD accounts (caching guids as we go).
            doToAccounts(createUser)
            
            # Patch the caldavd.plist file with the testadmin user's guid-based principal-URL
            if old_style:
                patchConfig(config, "/principals/users/testadmin/")
            else:
                patchConfig(config, "/principals/__uids__/%s/" % (guids["testadmin"],))
            
            # Create an appropriate serverinfo.xml file from the template
            buildServerinfo(hostname, docroot)

            # Add large calendars to user account
            addLargeCalendars(hostname, docroot)

        elif args[0] == "create-users":
            # Read the caldavd.plist file and extract some information we will need.
            hostname, docroot, sudoers = readConfig(config)
            
            # Now generate the OD accounts (caching guids as we go).
            doToAccounts(createUser, users_only=True)
            
            # Create an appropriate serverinfo.xml file from the template
            buildServerinfo(hostname, docroot)

        elif args[0] == "remove":
            doToAccounts(removeUser)
            
    except Exception, e:
        sys.exit(str(e))
