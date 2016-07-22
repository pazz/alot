# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import mailbox
import logging
import os
import glob

from alot.helper import call_cmd_async
from alot.helper import split_commandstring


class SendingMailFailed(RuntimeError):
    pass


class StoreMailError(Exception):
    pass


class _CaseInsensitiveUnicode(unicode):
    """A subclass of unicode that matches case insensitive.

    This behaves exactly like a standard Unicode object, except that it
    overrides the rich comparison methods and __contains__ to do case
    insensitve comparison.
    """
    # TODO: There are some cases that are not going to be handled correctly,
    # the strip methods, for example, will return a standard Unicode object
    # rather than a _CaseInsensitveUnicode.

    def __lt__(self, other):
        if isinstance(other, basestring):
            return super(_CaseInsensitiveUnicode, self).lower() < other.lower()
        return super(_CaseInsensitveStr, self).__lt__(other)

    def __le__(self, other):
        if isinstance(other, basestring):
            return super(_CaseInsensitiveUnicode, self).lower() <= other.lower()
        return super(_CaseInsensitveStr, self).__le__(other)

    def __gt__(self, other):
        if isinstance(other, basestring):
            return super(_CaseInsensitiveUnicode, self).lower() > other.lower()
        return super(_CaseInsensitveStr, self).__gt__(other)

    def __ge__(self, other):
        if isinstance(other, basestring):
            return super(_CaseInsensitiveUnicode, self).lower() >= other.lower()
        return super(_CaseInsensitveStr, self).__ge__(other)

    def __eq__(self, other):
        if isinstance(other, basestring):
            return super(_CaseInsensitiveUnicode, self).lower() == other.lower()
        return super(_CaseInsensitveStr, self).__eq__(other)

    def __ne__(self, other):
        if isinstance(other, basestring):
            return super(_CaseInsensitiveUnicode, self).lower() != other.lower()
        return super(_CaseInsensitveStr, self).__ne__(other)

    def __contains__(self, other):
        if isinstance(other, basestring):
            return other.lower() in super(_CaseInsensitiveUnicode, self).lower()
        return super(_CaseInsensitveStr, self).__contains__(other)

    def capitalize(self):
        return self

    def center(self, *args, **kwargs):
        return _CaseInsensitiveUnicode(
            super(_CaseInsensitiveUnicode, self).center(*args, **kwargs))

    def endswith(self, other, *args, **kwargs):
        return super(_CaseInsensitiveUnicode, self).lower().endswith(
            other.lower(), *args, **kwargs)

    def expandtabs(self, *args, **kwargs):
        return _CaseInsensitiveUnicode(
            super(_CaseInsensitiveUnicode, self).expandtabs(*args, **kwargs))

    def ljust(self, *args, **kwargs):
        return _CaseInsensitiveUnicode(
            super(_CaseInsensitiveUnicode, self).ljust(*args, **kwargs))

    def lower(self):
        return self

    def lstrip(self, *args, **kwargs):
        return _CaseInsensitiveUnicode(
            super(_CaseInsensitiveUnicode, self).lstrip(*args, **kwargs))

    def partition(self, *args, **kwargs):
        return tuple(_CaseInsensitiveUnicode(s) for s in 
                     super(_CaseInsensitiveUnicode, self).partition(
                         *args, **kwargs))

    def rjust(self, *args, **kwargs):
        return _CaseInsensitiveUnicode(
            super(_CaseInsensitiveUnicode, self).rjust(*args, **kwargs))

    def rpartition(self, *args, **kwargs):
        return tuple(_CaseInsensitiveUnicode(s) for s in 
                     super(_CaseInsensitiveUnicode, self).rpartition(
                         *args, **kwargs))

    def rsplit(self, sep, **kwargs):
        return [_CaseInsensitiveUnicode(s) for s in 
                super(_CaseInsensitiveUnicode, self).lower().rsplit(
                    sep.lower(), **kwargs)]

    def rstrip(self, *args, **kwargs):
        return _CaseInsensitiveUnicode(
            super(_CaseInsensitiveUnicode, self).rstrip(*args, **kwargs))

    def split(self, *args, **kwargs):
        return [_CaseInsensitiveUnicode(s) for s in 
                super(_CaseInsensitiveUnicode, self).lower().split(
                    sep.lower(), **kwargs)]

    def splitlines(self, *args, **kwargs):
        return [_CaseInsensitiveUnicode(s) for s in 
                super(_CaseInsensitiveUnicode, self).splitlines(*args, **kwargs)]

    def startswith(self, other, *args, **kwargs):
        return super(_CaseInsensitiveUnicode, self).lower().startswith(
            other.lower(), *args, **kwargs)

    def swapcase(self):
        return self

    def title(self):
        return self

    def translate(self, *args, **kwargs):
        return _CaseInsensitiveUnicode(
            super(_CaseInsensitiveUnicode, self).translate(*args, **kwargs))

    def upper(self):
        return self

    def zfill(self, *args, **kwargs):
        return _CaseInsensitiveUnicode(
            super(_CaseInsensitiveUnicode, self).zfill(*args, **kwargs))


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
    alias_regexp = []
    """regex matching alternative addresses"""
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
    """addressbook (:class:`addressbook.AddressBook`)
       managing this accounts contacts"""

    def __init__(self, address=None, aliases=None, alias_regexp=None,
                 realname=None, gpg_key=None, signature=None,
                 signature_filename=None, signature_as_attachment=False,
                 sent_box=None, sent_tags=['sent'], draft_box=None,
                 draft_tags=['draft'], abook=None, sign_by_default=False,
                 encrypt_by_default=False, non_standard_case_insensitive=False,
                 **rest):
        if non_standard_case_insensitive:
            address = _CaseInsensitiveUnicode(address)
        self.address = address
        self.aliases = aliases
        self.alias_regexp = alias_regexp
        self.realname = realname
        self.gpg_key = gpg_key
        self.signature = signature
        self.signature_filename = signature_filename
        self.signature_as_attachment = signature_as_attachment
        self.sign_by_default = sign_by_default
        self.encrypt_by_default = encrypt_by_default
        self.sent_box = sent_box
        self.sent_tags = sent_tags
        self.draft_box = draft_box
        self.draft_tags = draft_tags
        self.abook = abook

    def get_addresses(self):
        """return all email addresses connected to this account, in order of
        their importance"""
        return [self.address] + self.aliases

    def store_mail(self, mbx, mail):
        """
        stores given mail in mailbox. If mailbox is maildir, set the S-flag and
        return path to newly added mail. Oherwise this will return `None`.

        :param mbx: mailbox to use
        :type mbx: :class:`mailbox.Mailbox`
        :param mail: the mail to store
        :type mail: :class:`email.message.Message` or str
        :returns: absolute path of mail-file for Maildir or None if mail was
                  successfully stored
        :rtype: str or None
        :raises: StoreMailError
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

        try:
            message_id = mbx.add(msg)
            mbx.flush()
            mbx.unlock()
            logging.debug('got mailbox msg id : %s' % message_id)
        except Exception as e:
            raise StoreMailError(e)

        path = None
        # add new Maildir message to index and add tags
        if isinstance(mbx, mailbox.Maildir):
            # this is a dirty hack to get the path to the newly added file
            # I wish the mailbox module were more helpful...
            plist = glob.glob1(os.path.join(mbx._path, 'new'),
                               message_id + '*')
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
        cmdlist = split_commandstring(self.cmd)

        def cb(out):
            logging.info('sent mail successfully')
            logging.info(out)

        def errb(failure):
            termobj = failure.value
            errmsg = '%s failed with code %s:\n%s' % \
                (self.cmd, termobj.exitCode, str(failure.value))
            logging.error(errmsg)
            logging.error(failure.getTraceback())
            logging.error(failure.value.stderr)
            raise SendingMailFailed(errmsg)

        d = call_cmd_async(cmdlist, stdin=mail)
        d.addCallback(cb)
        d.addErrback(errb)
        return d
