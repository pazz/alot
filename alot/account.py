import mailbox
import logging
import time
import re
import email
import os
import glob
import shlex
from ConfigParser import SafeConfigParser
from urlparse import urlparse

import helper

class SendingMailFailed(RuntimeError): pass

class Account(object):
    """
    Datastructure that represents an email account. It manages this account's
    settings, can send and store mails to maildirs (drafts/send).

    .. note::

        This is an abstract class that leaves :meth:`send_mail` unspecified.
        See :class:`SendmailAccount` for a subclass that uses a sendmail
        command to send out mails.
    """

    address = None
    """this accounts main email address"""
    aliases = []
    """list of alternative addresses"""
    realname = None
    """real name used to format from-headers"""
    gpg_key = None
    """gpg fingerprint for this account's private key"""
    signature = None
    """signature to append to outgoing mails"""
    signature_filename = None
    """filename of signature file in attachment"""
    abook = None
    """addressbook (:class:`AddressBook`) managing this accounts contacts"""

    def __init__(self, dbman, address=None, aliases=None, realname=None,
                 gpg_key=None, signature=None, signature_filename=None,
                 sent_box=None, sent_tags=['sent'], draft_box=None,
                 draft_tags=['draft'], abook=None):
        self.dbman = dbman
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
        self.sent_tags = sent_tags

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
        self.draft_tags = draft_tags

    def store_mail(self, mbx, mail, tags = None):
        """
        stores given mail in mailbox. If mailbox is maildir, set the S-flag.

        :param mbx: mailbox to use
        :type mbx: :class:`mailbox.Mailbox`
        :param mail: the mail to store
        :type mail: :class:`email.message.Message` or str
        :param tags: if given, add the mail to the notmuch index and tag it
        :type tags: list of str
        :returns: True iff mail was successfully stored
        :rtype: bool
        """
        if not isinstance(mbx, mailbox.Mailbox):
            logging.debug('Not a mailbox')
            return False
        else:
            mbx.lock()
            if isinstance(mbx, mailbox.Maildir):
                logging.debug('Maildir')
                msg = mailbox.MaildirMessage(mail)
                msg.set_flags('S')
            else:
                logging.debug('no Maildir')
                msg = mailbox.Message(mail)
            id = mbx.add(msg)
            mbx.flush()
            mbx.unlock()
            logging.debug('got id : %s' % id)
            return True

        if isinstance(mbx, mailbox.Maildir) and tags != None:
            # this is a dirty hack to get the path to the newly added file
            # I wish the mailbox module were more helpful...
            path = glob.glob(os.path.join(mbx._path, '*', message_id + '*'))[0]

            message = self.dbman.add_message(path)
            message.add_tags(tags)
            self.dbman.flush()

    def store_sent_mail(self, mail):
        """
        stores mail (:class:`email.message.Message` or str) in send-store if
        :attr:`sent_box` is set.
        """
        if self.sent_box is not None:
            self.store_mail(self.sent_box, mail, self.sent_tags)

    def store_draft_mail(self, mail):
        """
        stores mail (:class:`email.message.Message` or str) as draft if
        :attr:`draft_box` is set.
        """
        if self.draft_box is not None:
            self.store_mail(self.sent_box, mail, self.draft_tags)

    def send_mail(self, mail):
        """
        sends given mail

        :param mail: the mail to send
        :type mail: :class:`email.message.Message` or string
        :raises: :class:`alot.account.SendingMailFailed` if an error occured
        """
        return 'not implemented'


class SendmailAccount(Account):
    """:class:`Account` that pipes a message to a `sendmail` shell command for
    sending"""
    def __init__(self, dbman, cmd, **kwargs):
        """
        :param dbman: the database manager instance
        :type dbman: :class:`~alot.db.DBManager`
        :param cmd: sendmail command to use for this account
        :type cmd: str
        """
        super(SendmailAccount, self).__init__(dbman, **kwargs)
        self.cmd = cmd

    def send_mail(self, mail):
        mail['Date'] = email.utils.formatdate(time.time(), True)
        cmdlist = shlex.split(self.cmd.encode('utf-8', errors='ignore'))
        out, err, retval = helper.call_cmd(cmdlist, stdin=mail.as_string())
        if err:
            raise SendingMailFailed('%s. sendmail_cmd set to: %s' % (err, self.cmd))
        self.store_sent_mail(mail)


class AccountManager(object):
    """
    creates and organizes multiple :class:`Accounts <Account>` that were
    defined in the "account" sections of a given
    :class:`~alot.settings.AlotConfigParser`.
    """
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
               'sent_tags',
               'draft_box',
               'draft_tags']
    manditory = ['realname', 'address']
    parse_lists = ['sent_tags', 'draft_tags']
    accountmap = {}
    accounts = []
    ordered_addresses = []

    def __init__(self, dbman, config):
        """
        :param dbman: the database manager instance
        :type dbman: :class:`~alot.db.DBManager`
        :param config: the config object to read account information from
        :type config: :class:`~alot.settings.AlotConfigParser`.
        """
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
                    regexp = config.get(s, 'abook_regexp')
                    options.remove('abook_regexp')
                else:
                    regexp = None  # will use default in constructor
                args['abook'] = MatchSdtoutAddressbook(cmd, match=regexp)

            to_set = self.manditory
            for o in options:
                if o not in self.parse_lists:
                    args[o] = config.get(s, o)
                else:
                    args[o] = config.getstringlist(s, o)
                if o in to_set:
                    to_set.remove(o)  # removes obligation
            if not to_set:  # all manditory fields were present
                sender_type = args.pop('type', 'sendmail')
                if sender_type == 'sendmail':
                    cmd = args.pop('sendmail_command', 'sendmail')
                    newacc = (SendmailAccount(dbman, cmd, **args))
                    self.accountmap[newacc.address] = newacc
                    self.accounts.append(newacc)
                    for alias in newacc.aliases:
                        self.accountmap[alias] = newacc
            else:
                logging.info('account section %s lacks %s' % (s, to_set))

    def get_accounts(self):
        """
        returns known accounts

        :rtype: list of :class:`Account`
        """
        return self.accounts

    def get_account_by_address(self, address):
        """
        returns :class:`Account` for a given email address (str)

        :param address: address to look up
        :type address: string
        :rtype:  :class:`Account` or None
        """

        for myad in self.get_addresses():
            if myad in address:
                return self.accountmap[myad]
        return None

    def get_main_addresses(self):
        """returns addresses of known accounts without its aliases"""
        return [a.address for a in self.accounts]

    def get_addresses(self):
        """returns addresses of known accounts including all their aliases"""
        return self.accountmap.keys()

    def get_addressbooks(self, order=[], append_remaining=True):
        """returns list of all defined :class:`AddressBook` objects"""
        abooks = []
        for a in order:
            if a:
                if a.abook:
                    abooks.append(a.abook)
        if append_remaining:
            for a in self.accounts:
                if a.abook and a.abook not in abooks:
                    abooks.append(a.abook)
        return abooks


class AddressBook(object):
    """can look up email addresses and realnames for contacts.

    .. note::

        This is an abstract class that leaves :meth:`get_contacts`
        unspecified. See :class:`AbookAddressBook` and
        :class:`MatchSdtoutAddressbook` for implementations.
    """

    def get_contacts(self):
        """list all contacts tuples in this abook as (name, email) tuples"""
        return []

    def lookup(self, prefix=''):
        """looks up all contacts with given prefix (in name or address)"""
        res = []
        for name, email in self.get_contacts():
            if name.startswith(prefix) or email.startswith(prefix):
                res.append("%s <%s>" % (name, email))
        return res


class AbookAddressBook(AddressBook):
    """:class:`AddressBook` that parses abook's config/database files"""
    def __init__(self, config=None):
        """
        :param config: path to an `abook` contacts file
                       (defaults to '/.abook/addressbook')
        :type config: str
        """
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
    """:class:`AddressBook` that parses a shell command's output for lookups"""
    def __init__(self, command, match=None):
        """
        :param command: lookup command
        :type command: str
        :param match: regular expression used to match contacts in `commands`
                      output to stdout. Must define subparts named "email" and
                      "name". Defaults to "(?P<email>.+?@.+?)\s+(?P<name>.+)".
        :type match: str
        """
        self.command = command
        if not match:
            self.match = "(?P<email>.+?@.+?)\s+(?P<name>.+)"
        else:
            self.match = match

    def get_contacts(self):
        return self.lookup('\'\'')

    def lookup(self, prefix):
        cmdlist = shlex.split(self.command.encode('utf-8', errors='ignore'))
        resultstring, errmsg, retval = helper.call_cmd(cmdlist + [prefix])
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
