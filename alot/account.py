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

from send import SendmailSender


class Account:
    def __init__(self, address, realname=None,
             gpg_key=None,
             signature=None,
             sender_type='sendmail',
             sendmail_command='sendmail',
             sent_mailbox=None):
        self.address = address
        self.realname = realname
        self.gpg_key = gpg_key
        self.signature = signature
        self.sender_type = sender_type

        if sent_mailbox:
            #parse mailbox url
            self.mailbox = mailbox.Maildir(sent_mailbox)
        else:
            self.mailbox = sent_mailbox

        if self.sender_type == 'sendmail':
            self.sender = SendmailSender(sendmail_command,
                                         mailbox=self.mailbox)
