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
from urlparse import urlparse

from send import SendmailSender


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
    """gpg fingerprint :note:currently ignored"""
    signature = None
    """signature to append to outgoing mails note::currently ignored"""

    def __init__(self, address=None, aliases=None, realname=None, gpg_key=None,
                 signature=None, sent_box=None, draft_box=None):
        self.address = address
        self.aliases = []
        if aliases:
            self.aliases = aliases.split(';')
        self.realname = realname
        self.gpg_key = gpg_key
        self.signature = signature

        self.sent_box = None
        if sent_box:
            mburl = urlparse(sent_mailbox)
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
            mburl = urlparse(sent_mailbox)
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
        :type mbx: `mailbox.Mailbox`
        :type mail: `email.message.Message` or string
        """
        mbx.lock()
        if isinstance(mbx, mailbox.Maildir):
            msg = mailbox.MaildirMessage(email)
            msg.set_flags('S')
        else:
            msg = mailbox.Message(email)
        key = mbx.add(email)
        mbx.flush()
        mbx.unlock()

    def store_sent_mail(self, mail):
        """stores given mail as sent if sent_box is set"""
        if self.sent_box:
            self.store_mail(self.sent_box, mail)

    def store_draft_mail(self, mail):
        """stores given mail as draft if draft_box is set"""
        if self.draft_box:
            self.store_mail(self.sent_box, mail)

    def send_mail(self, email):
        """
        sends given email
        :returns: tuple (success, reason) of types bool and str.
        """
        return False, 'not implemented'


class SendmailAccount(Account):
    """Account that knows how to send out mails via sendmail"""
    def __init__(self, cmd, **kwargs):
        Account.__init__(self, **kwargs)
        self.cmd = cmd

    def send_mail(self, mail):
        mail['Date'] = email.utils.formatdate(time.time(), True)
        # no unicode in shlex on 2.x
        args = shlex.split(self.cmd.encode('ascii'))
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            out, err = proc.communicate(mail.as_string())
        except OSError, e:
            return False, str(e) + '. sendmail_cmd set to: %s' % self.cmd
        if proc.poll():  # returncode is not 0
            return False, err.strip()
        else:
            self.store_sent_mail(mail)
            return True, ''


class AccountManager:
    allowed = ['realname',
               'address',
               'aliases',
               'gpg_key',
               'signature',
               'type',
               'sendmail_command',
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
                logging.info('account section %s lacks fields %s' % (s, to_set))

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
