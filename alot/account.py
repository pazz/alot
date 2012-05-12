import mailbox
import logging
import time
import email
import os
import glob
import shlex

from alot.helper import call_cmd_async
import alot.crypto as crypto


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
    """addressbook (:class:`addressbooks.AddressBook`)
       managing this accounts contacts"""

    def __init__(self, address=None, aliases=None, realname=None,
                 gpg_key=None, signature=None, signature_filename=None,
                 signature_as_attachment=False, sent_box=None,
                 sent_tags=['sent'], draft_box=None, draft_tags=['draft'],
                 abook=None, sign_by_default=False, **rest):
        self.address = address
        self.aliases = aliases
        self.realname = realname
        self.gpg_key = gpg_key
        self.signature = signature
        self.signature_filename = signature_filename
        self.signature_as_attachment = signature_as_attachment
        self.sign_by_default = sign_by_default
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

        d = call_cmd_async(cmdlist, stdin=crypto.email_as_string(mail))
        d.addCallback(cb)
        d.addErrback(errb)
        return d
