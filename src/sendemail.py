#
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
#
# DRI: Cyrus Daboo, cdaboo@apple.com
##

"""
Send an email message.
"""

import email.mime.text
import smtplib

def sendemail(fromaddr=("", ""), toaddrs=[], subject="", body=""):
    """
    
    @param fromaddr: tuple of From address (<full name>, <email>)
    @param toaddrs: list of tuples of (<full name>, <email>) for each recipient
    @param subject: a C{str} containing the subject
    @param body: a C{str} containing the body
    """
    
    def fulladdr(addr):
        if addr[0]:
            return "%s <%s>" % (addr[0], addr[1],)
        else:
            return addr[1]

    if isinstance(body, unicode):
        body = body.decode("utf-8")
    charset = "us-ascii"
    for c in body:
        if ord(c) > 0x7F:
            charset = "utf-8"
            break
    msg = email.mime.text.MIMEText(body, "plain", charset)
    msg.add_header("From", fulladdr(fromaddr))
    msg.add_header("To", ", ".join([fulladdr(a) for a in toaddrs]))
    msg.add_header("Subject", subject)
    msgtxt = msg.as_string(False)
    server = smtplib.SMTP("relay.apple.com")
    server.sendmail(fromaddr[1], [a[1] for a in toaddrs], msgtxt)
    server.quit()
