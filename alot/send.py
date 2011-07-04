"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Alot is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""

import mailbox
import shlex
import subprocess
import logging
import time
import email


class Sender:
    def send_mail(self, email):
        pass

    def __init__(self, mailbox=None):
        self.mailbox = mailbox

    def store_mail(self, email):
        if self.mailbox:
            self.mailbox.lock()
            if isinstance(self.mailbox, mailbox.Maildir):
                msg = mailbox.MaildirMessage(email)
                msg.set_flags('S')
            else:
                msg = mailbox.Message(email)
            key = self.mailbox.add(email)
            self.mailbox.flush()
            self.mailbox.unlock()


class SendmailSender(Sender):

    def __init__(self, sendmail_cmd, mailbox=None):
        self.cmd = sendmail_cmd
        self.mailbox = mailbox

    def send_mail(self, mail):
        mail['Date'] = email.utils.formatdate(time.time(), True)
        args = shlex.split(self.cmd)
        proc = subprocess.Popen(args, stdin=subprocess.PIPE)
        proc.communicate(mail.as_string())
        self.store_mail(mail)
        return True
