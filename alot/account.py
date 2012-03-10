import mailbox
import logging
import time
import re
import email
import os
import glob
import shlex
from urlparse import urlparse

import helper


class SendingMailFailed(RuntimeError):
    pass


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
    signature_as_attachment = None
    """attach signature file instead of appending its content to body text"""
    abook = None
    """addressbook (:class:`AddressBook`) managing this accounts contacts"""

    def __init__(self, address=None, aliases=None, realname=None,
                 gpg_key=None, signature=None, signature_filename=None,
                 signature_as_attachment=False, sent_box=None,
                 sent_tags=['sent'], draft_box=None, draft_tags=['draft'],
                 abook=None, **rest):
        self.address = address
        self.abook = abook
        self.aliases = []
        self.aliases = aliases
        self.realname = realname
        self.gpg_key = gpg_key
        self.signature = signature
        self.signature_filename = signature_filename
        self.signature_as_attachment = signature_as_attachment

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

    def get_addresses(self):
        """return all email addresses connected to this account, in order of
        their importance"""
        return [self.address] + self.aliases

    def store_mail(self, mbx, mail):
        """
        stores given mail in mailbox. If mailbox is maildir, set the S-flag.

        :param mbx: mailbox to use
        :type mbx: :class:`mailbox.Mailbox`
        :param mail: the mail to store
        :type mail: :class:`email.message.Message` or str
        :returns: absolute path of mail-file for Maildir or None if mail was
                  successfully stored
        :rtype: str or None
        """
        if not isinstance(mbx, mailbox.Mailbox):
            logging.debug('Not a mailbox')
            return False

        mbx.lock()
        if isinstance(mbx, mailbox.Maildir):
            logging.debug('Maildir')
            msg = mailbox.MaildirMessage(mail)
            msg.set_flags('S')
        else:
            logging.debug('no Maildir')
            msg = mailbox.Message(mail)

        message_id = mbx.add(msg)
        mbx.flush()
        mbx.unlock()
        logging.debug('got id : %s' % id)

        path = None
        # add new Maildir message to index and add tags
        if isinstance(mbx, mailbox.Maildir):
            # this is a dirty hack to get the path to the newly added file
            # I wish the mailbox module were more helpful...
            plist = glob.glob1(os.path.join(mbx._path, 'new'), message_id + '*')
            if plist:
                path = os.path.join(mbx._path, 'new', plist[0])
                logging.debug('path of saved msg: %s' % path)
        return path

    def store_sent_mail(self, mail):
        """
        stores mail (:class:`email.message.Message` or str) in send-store if
        :attr:`sent_box` is set.
        """
        if self.sent_box is not None:
            return self.store_mail(self.sent_box, mail)

    def store_draft_mail(self, mail):
        """
        stores mail (:class:`email.message.Message` or str) as draft if
        :attr:`draft_box` is set.
        """
        if self.draft_box is not None:
            return self.store_mail(self.draft_box, mail)

    def send_mail(self, mail):
        """
        sends given mail

        :param mail: the mail to send
        :type mail: :class:`email.message.Message` or string
        :returns: a `Deferred` that errs back with a class:`SendingMailFailed`,
                  containing a reason string if an error occured.
        """
        raise NotImplementedError


class SendmailAccount(Account):
    """:class:`Account` that pipes a message to a `sendmail` shell command for
    sending"""
    def __init__(self, cmd, **kwargs):
        """
        :param cmd: sendmail command to use for this account
        :type cmd: str
        """
        super(SendmailAccount, self).__init__(**kwargs)
        self.cmd = cmd

    def send_mail(self, mail):
        mail['Date'] = email.utils.formatdate(time.time(), True)
        cmdlist = shlex.split(self.cmd.encode('utf-8', errors='ignore'))

        def cb(out):
            logging.info('sent mail successfully')
            logging.info(out)

        def errb(failure):
            termobj = failure.value
            errmsg = '%s\nsendmail_cmd set to: %s' % (str(termobj), self.cmd)
            logging.error(errmsg)
            logging.error(failure.getTraceback())
            logging.error(failure.value.stderr)
            raise SendingMailFailed(errmsg)

        d = helper.call_cmd_async(cmdlist, stdin=mail.as_string())
        d.addCallback(cb)
        d.addErrback(errb)
        return d


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
                res.append((name, email))
        return res


class AbookAddressBook(AddressBook):
    """:class:`AddressBook` that parses abook's config/database files"""
    def __init__(self, path='~/.abook/addressbook'):
        """
        :param path: path to theme file
        :type path: str
        """
        DEFAULTSPATH = os.path.join(os.path.dirname(__file__), 'defaults')
        self._spec = os.path.join(DEFAULTSPATH, 'abook_contacts.spec')
        path = os.path.expanduser(path)
        self._config = helper.read_config(path, self._spec)
        del(self._config['format'])

    def get_contacts(self):
        c = self._config
        return [(c[id]['name'], c[id]['email']) for id in c.sections if \
                c[id]['email'] is not None]


class MatchSdtoutAddressbook(AddressBook):
    """:class:`AddressBook` that parses a shell command's output for lookups"""
    def __init__(self, command, match=None):
        """
        :param command: lookup command
        :type command: str
        :param match: regular expression used to match contacts in `commands`
                      output to stdout. Must define subparts named "email" and
                      "name".  Defaults to
                      :regexp:`^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)`.
        :type match: str
        """
        self.command = command
        if not match:
            self.match = '^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)'
        else:
            self.match = match

    def get_contacts(self):
        return self.lookup('\'\'')

    def lookup(self, prefix):
        cmdlist = shlex.split(self.command.encode('utf-8', errors='ignore'))
        resultstring, errmsg, retval = helper.call_cmd(cmdlist + [prefix])
        if not resultstring:
            return []
        lines = resultstring.splitlines()
        res = []
        for l in lines:
            m = re.match(self.match, l)
            if m:
                info = m.groupdict()
                email = info['email'].strip()
                name = info['name']
                res.append((name, email))
        return res
