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
import re
import email
import os
from ConfigParser import SafeConfigParser
from urlparse import urlparse

from helper import cmd_output
import helper


class Account:
    """
    Datastructure that represents an email account. It manages
    this account's settings, can send and store mails to
    maildirs (drafts/send)
    """

    address = None
    """this accounts main email address"""
    aliases = []
    """list of alternative addresses"""
    realname = None
    """real name used to format from-headers"""
    gpg_key = None
    """gpg fingerprint. CURRENTLY IGNORED"""
    signature = None
    """signature to append to outgoing mails"""
    signature_filename = None
    """filename of signature file in attachment"""
    abook = None
    """addressbook"""

    def __init__(self, address=None, aliases=None, realname=None, gpg_key=None,
                 signature=None, signature_filename=None, sent_box=None,
                 draft_box=None, abook=None):

        self.address = address
        self.abook = abook
        self.aliases = []
        if aliases:
            self.aliases = aliases.split(';')
        self.realname = realname
        self.gpg_key = gpg_key
        self.signature = signature
        self.signature_filename = signature_filename

        self.sent_box = None
        if sent_box:
            mburl = urlparse(sent_box)
            if mburl.scheme == 'mbox':
                self.sent_box = mailbox.mbox(mburl.path)
            elif mburl.scheme == 'maildir':
                self.sent_box = mailbox.Maildir(mburl.path)
            elif mburl.scheme == 'mh':
                self.sent_box = mailbox.MH(mburl.path)
            elif mburl.scheme == 'babyl':
                self.sent_box = mailbox.Babyl(mburl.path)
            elif mburl.scheme == 'mmdf':
                self.sent_box = mailbox.MMDF(mburl.path)

        self.draft_box = None
        if draft_box:
            mburl = urlparse(draft_box)
            if mburl.scheme == 'mbox':
                self.draft_box = mailbox.mbox(mburl.path)
            elif mburl.scheme == 'maildir':
                self.draft_box = mailbox.Maildir(mburl.path)
            elif mburl.scheme == 'mh':
                self.draft_box = mailbox.MH(mburl.path)
            elif mburl.scheme == 'babyl':
                self.draft_box = mailbox.Babyl(mburl.path)
            elif mburl.scheme == 'mmdf':
                self.draft_box = mailbox.MMDF(mburl.path)

    def store_mail(self, mbx, mail):
        """stores given mail in mailbox. if mailbox is maildir, set the S-flag.

        :param mbx: mailbox to use
        :type mbx: `mailbox.Mailbox`
        :param mail: the mail to store
        :type mail: `email.message.Message` or string
        """
        mbx.lock()
        if isinstance(mbx, mailbox.Maildir):
            msg = mailbox.MaildirMessage(mail)
            msg.set_flags('S')
        else:
            msg = mailbox.Message(mail)
        key = mbx.add(mail)
        mbx.flush()
        mbx.unlock()

    def store_sent_mail(self, mail):
        """stores mail in send-store if sent_box is set

        :param mail: the mail to store
        :type mail: `email.message.Message` or string
        """
        if self.sent_box:
            self.store_mail(self.sent_box, mail)

    def store_draft_mail(self, mail):
        """stores mail as draft if draft_box is set

        :param mail: the mail to store
        :type mail: `email.message.Message` or string
        """
        if self.draft_box:
            self.store_mail(self.sent_box, mail)

    def send_mail(self, mail):
        """
        sends given mail

        :param mail: the mail to send
        :type mail: `email.message.Message` or string
        :returns: None if successful and a string with the reason
                  for failure otherwise
        """
        return 'not implemented'


class SendmailAccount(Account):
    """Account that knows how to send out mails via sendmail"""
    def __init__(self, cmd, **kwargs):
        Account.__init__(self, **kwargs)
        self.cmd = cmd

    def send_mail(self, mail):
        mail['Date'] = email.utils.formatdate(time.time(), True)
        out, err = helper.pipe_to_command(self.cmd, mail.as_string())
        if err:
            return err + '. sendmail_cmd set to: %s' % self.cmd
        self.store_sent_mail(mail)
        return None


class AccountManager:
    """Easy access to all known accounts"""
    allowed = ['realname',
               'address',
               'aliases',
               'gpg_key',
               'signature',
               'signature_filename',
               'type',
               'sendmail_command',
               'abook_command',
               'abook_regexp',
               'sent_box',
               'draft_box']
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
            if 'abook_command' in options:
                cmd = config.get(s, 'abook_command').encode('ascii',
                                                            errors='ignore')
                options.remove('abook_command')
                if 'abook_regexp' in options:
                    rgexp = config.get(s, 'abook_regexp')
                    options.remove('abook_regexp')
                else:
                    regexp = None  # will use default in constructor
                args['abook'] = MatchSdtoutAddressbook(cmd, match=regexp)

            to_set = self.manditory
            for o in options:
                args[o] = config.get(s, o)
                if o in to_set:
                    to_set.remove(o)  # removes obligation
            if not to_set:  # all manditory fields were present
                sender_type = args.pop('type', 'sendmail')
                if sender_type == 'sendmail':
                    cmd = args.pop('sendmail_command', 'sendmail')
                    newacc = (SendmailAccount(cmd, **args))
                    self.accountmap[newacc.address] = newacc
                    self.accounts.append(newacc)
                    for alias in newacc.aliases:
                        self.accountmap[alias] = newacc
            else:
                logging.info('account section %s lacks %s' % (s, to_set))

    def get_accounts(self):
        """return known accounts

        :rtype: list of `account.Account`
        """
        return self.accounts

    def get_account_by_address(self, address):
        """returns account for given email address

        :param address: address to look up
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

    def get_addressbooks(self):
        return [a.abook for a in self.accounts if a.abook]


class AddressBook:
    def get_contacts(self):
        return []

    def lookup(self, prefix=''):
        res = []
        for name, email in self.get_contacts():
            if name.startswith(prefix) or email.startswith(prefix):
                res.append("%s <%s>" % (name, email))
        return res


class AbookAddressBook(AddressBook):
    def __init__(self, config=None):
        self.abook = SafeConfigParser()
        if not config:
            config = os.environ["HOME"] + "/.abook/addressbook"
        self.abook.read(config)

    def get_contacts(self):
        res = []
        for s in self.abook.sections():
            if s.isdigit():
                name = self.abook.get(s, 'name')
                email = self.abook.get(s, 'email')
                res.append((name, email))
        return res


class MatchSdtoutAddressbook(AddressBook):
    def __init__(self, command, match=None):
        self.command = command
        if not match:
            self.match = "(?P<email>.+?@.+?)\s+(?P<name>.+)"
        else:
            self.match = match

    def get_contacts(self):
        return self.lookup('\'\'')

    def lookup(self, prefix):
        resultstring = cmd_output('%s %s' % (self.command, prefix))
        if not resultstring:
            return []
        lines = resultstring.replace('\t', ' ' * 4).splitlines()
        res = []
        for l in lines:
            m = re.match(self.match, l)
            if m:
                info = m.groupdict()
                email = info['email'].strip()
                name = info['name'].strip()
                res.append((name, email))
        return res
