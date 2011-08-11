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
from urlparse import urlparse

from send import SendmailSender


class Account:
    def __init__(self, address, aliases=None, realname=None, gpg_key=None, signature=None,
                 sender_type='sendmail', sendmail_command='sendmail',
                 sent_mailbox=None):
        self.address = address
        self.aliases = []
        if aliases:
            self.aliases = aliases.split(';')
        self.realname = realname
        self.gpg_key = gpg_key
        self.signature = signature
        self.sender_type = sender_type

        self.mailbox = None
        if sent_mailbox:
            mburl = urlparse(sent_mailbox)
            if mburl.scheme == 'mbox':
                self.mailbox = mailbox.mbox(mburl.path)
            elif mburl.scheme == 'maildir':
                self.mailbox = mailbox.Maildir(mburl.path)
            elif mburl.scheme == 'mh':
                self.mailbox = mailbox.MH(mburl.path)
            elif mburl.scheme == 'babyl':
                self.mailbox = mailbox.Babyl(mburl.path)
            elif mburl.scheme == 'mmdf':
                self.mailbox = mailbox.MMDF(mburl.path)

        if self.sender_type == 'sendmail':
            self.sender = SendmailSender(sendmail_command,
                                         mailbox=self.mailbox)


class AccountManager:
    allowed = ['realname',
               'address',
               'aliases',
               'gpg_key',
               'signature',
               'sender_type',
               'sendmail_command',
               'sent_mailbox']
    manditory = ['realname', 'address']
    accountmap = {}
    accounts = []
    ordered_addresses = []

    def __init__(self, config):
        sections = config.sections()
        accountsections = filter(lambda s: s.startswith('account '), sections)
        for s in accountsections:
            options = filter(lambda x: x in self.allowed, config.options(s))
            args = {}
            for o in options:
                args[o] = config.get(s, o)
                if o in self.manditory:
                    self.manditory.remove(o)
            if not self.manditory:
                newacc = (Account(**args))
                self.accountmap[newacc.address] = newacc
                self.accounts.append(newacc)
                for alias in newacc.aliases:
                    self.accountmap[alias] = newacc
            else:
                pass
                # log info

    def get_accounts(self):
        """return known accounts

        :rtype: list of `account.Account`
        """
        return self.accounts

    def get_account_by_address(self, address):
        """returns account for given email address

        :type address: string
        :rtype:  `account.Account` or None
        """

        if address in self.accountmap:
            return self.accountmap[address]
        else:
            return None
            # log info

    def get_main_addresses(self):
        """returns addresses of known accounts without its aliases"""
        return [a.address for a in self.accounts]

    def get_addresses(self):
        """returns addresses of known accounts including all their aliases"""
        return self.accountmap.keys()
