# encoding=utf-8
# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2017 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import glob
import logging
import mailbox
import os
import re
import shlex
from email.message import Message
from typing import Any

from .addressbook import AddressBook
from .helper import call_cmd_async


class Address:

    """A class that represents an email address.

    This class implements a number of RFC requirements (as explained in detail
    below) specifically in the comparison of email addresses to each other.

    This class abstracts the requirements of RFC 5321 § 2.4 on the user name
    portion of the email:

        local-part of a mailbox MUST BE treated as case sensitive. Therefore,
        SMTP implementations MUST take care to preserve the case of mailbox
        local-parts. In particular, for some hosts, the user "smith" is
        different from the user "Smith".  However, exploiting the case
        sensitivity of mailbox local-parts impedes interoperability and is
        discouraged. Mailbox domains follow normal DNS rules and are hence not
        case sensitive.

    This is complicated by § 2.3.11 of the same RFC:

        The standard mailbox naming convention is defined to be
        "local-part@domain"; contemporary usage permits a much broader set of
        applications than simple "user names". Consequently, and due to a long
        history of problems when intermediate hosts have attempted to optimize
        transport by modifying them, the local-part MUST be interpreted and
        assigned semantics only by the host specified in the domain part of the
        address.

    And also the restrictions that RFC 1035 § 3.1 places on the domain name:

        Name servers and resolvers must compare [domains] in a case-insensitive
        manner

    Because of RFC 6531 § 3.2, we take special care to ensure that unicode
    names will work correctly:

        An SMTP server that announces the SMTPUTF8 extension MUST be prepared
        to accept a UTF-8 string [RFC3629] in any position in which RFC 5321
        specifies that a <mailbox> can appear.  Although the characters in the
        <local-part> are permitted to contain non-ASCII characters, the actual
        parsing of the <local-part> and the delimiters used are unchanged from
        the base email specification [RFC5321]

    What this means is that the username can be either case-insensitive or not,
    but only the receiving SMTP server can know what it's own rules are. The
    consensus is that the vast majority (all?) of the SMTP servers in modern
    usage treat user names as case-insensitve. Therefore we also, by default,
    treat the user name as case insenstive.

    :param str user: The "user name" portion of the address.
    :param str domain: The domain name portion of the address.
    :param bool case_sensitive: If False (the default) the user name portion of
        the address will be compared to the other user name portion without
        regard to case. If True then it will.
    """

    def __init__(self, user: str, domain: str,
                 case_sensitive: bool = False) -> None:
        assert isinstance(user, str), 'Username must be str'
        assert isinstance(domain, str), 'Domain name must be str'
        self.username = user
        self.domainname = domain
        self.case_sensitive = case_sensitive

    @classmethod
    def from_string(cls, address: str, case_sensitive: bool = False) -> 'Address':
        """Alternate constructor for building from a string.

        :param address: An email address in <user>@<domain> form
        :param case_sensitive: passed directly to the constructor argument
            of the same name.
        """
        assert isinstance(address, str), 'address must be str'
        username, domainname = address.split('@')
        return cls(username, domainname, case_sensitive=case_sensitive)

    def __repr__(self) -> str:
        return 'Address({!r}, {!r}, case_sensitive={})'.format(
            self.username,
            self.domainname,
            str(self.case_sensitive))

    def __str__(self) -> str:
        return '{}@{}'.format(self.username, self.domainname)

    def __eq__(self, other: object) -> bool:
        """Compare to another :class:`~alot.account.Address` or a `str`.

        The username is compared case-insensitively unless the address is
        case sensitive; the domain name always is.
        """
        if isinstance(other, str):
            try:
                ouser, odomain = other.split('@')
            except ValueError:
                ouser, odomain = '', ''
        elif isinstance(other, Address):
            ouser = other.username
            odomain = other.domainname
        else:
            raise TypeError('Address must be compared to Address or str')

        username = self.username
        if not self.case_sensitive:
            ouser = ouser.lower()
            username = username.lower()

        return (username == ouser and
                self.domainname.lower() == odomain.lower())

    def __hash__(self) -> int:
        return hash((self.username.lower(), self.domainname.lower(),
                     self.case_sensitive))


class SendingMailFailed(RuntimeError):
    pass


class StoreMailError(Exception):
    pass


class Account:
    """
    Datastructure that represents an email account. It manages this account's
    settings, can send and store mails to maildirs (drafts/send).

    .. note::
        This is an abstract class that leaves :meth:`send_mail` unspecified.
        See :class:`SendmailAccount` for a subclass that uses a sendmail
        command to send out mails.
    """

    address: Address
    """this accounts main email address"""
    aliases: list[Address]
    """list of alternative addresses"""
    alias_regexp: str | None
    """regex matching alternative addresses"""
    realname: str | None
    """real name used to format from-headers"""
    encrypt_to_self: bool | None
    """encrypt outgoing encrypted emails to this account's private key"""
    gpg_key: Any
    """the :class:`gpg.gpgme._gpgme_key` for this account's private key"""
    signature: str | None
    """signature to append to outgoing mails"""
    signature_filename: str | None
    """filename of signature file in attachment"""
    signature_as_attachment: bool
    """attach signature file instead of appending its content to body text"""
    abook: AddressBook | None
    """addressbook managing this accounts contacts"""

    def __init__(self, address: str, aliases: list[str] | None = None,
                 alias_regexp: str | None = None,
                 realname: str | None = None, gpg_key: Any = None,
                 signature: str | None = None,
                 signature_filename: str | None = None,
                 signature_as_attachment: bool = False,
                 sent_box: mailbox.Mailbox | None = None,
                 sent_tags: list[str] | None = None,
                 draft_box: mailbox.Mailbox | None = None,
                 draft_tags: list[str] | None = None,
                 replied_tags: list[str] | None = None,
                 passed_tags: list[str] | None = None,
                 abook: AddressBook | None = None,
                 sign_by_default: bool = False,
                 encrypt_by_default: str = "none",
                 encrypt_to_self: bool | None = None,
                 message_id_domain: str | None = None,
                 case_sensitive_username: bool = False, **_: Any) -> None:
        self.address = Address.from_string(
            address, case_sensitive=case_sensitive_username)
        self.aliases = [
            Address.from_string(a, case_sensitive=case_sensitive_username)
            for a in (aliases or [])]
        self.alias_regexp = alias_regexp
        self.realname = realname
        self.encrypt_to_self = encrypt_to_self
        self.gpg_key = gpg_key
        self.signature = signature
        self.signature_filename = signature_filename
        self.signature_as_attachment = signature_as_attachment
        self.sign_by_default = sign_by_default
        self.sent_box = sent_box
        self.sent_tags = sent_tags
        self.draft_box = draft_box
        self.draft_tags = draft_tags
        self.replied_tags = replied_tags
        self.passed_tags = passed_tags
        self.abook = abook
        self.message_id_domain = message_id_domain
        # Handle encrypt_by_default in an backwards compatible way.  The
        # logging info call can later be upgraded to warning or error.
        encrypt_by_default = encrypt_by_default.lower()
        msg = "Deprecation warning: The format for the encrypt_by_default " \
              "option changed.  Please use 'none', 'all' or 'trusted'."
        if encrypt_by_default in ("true", "yes", "1"):
            encrypt_by_default = "all"
            logging.info(msg)
        elif encrypt_by_default in ("false", "no", "0"):
            encrypt_by_default = "none"
            logging.info(msg)
        self.encrypt_by_default = encrypt_by_default
        # cache alias_regexp regexes
        self._alias_regexp = self.alias_regexp and re.compile(
            self.alias_regexp,
            flags=0 if case_sensitive_username else re.IGNORECASE)

    def matches_address(self, address: str) -> bool:
        """returns whether this account knows about an email address

        :param address: address to look up
        """
        if self.address == address:
            return True
        for alias in self.aliases:
            if alias == address:
                return True
        if self._alias_regexp and self._alias_regexp.fullmatch(address):
            return True
        return False

    @staticmethod
    def store_mail(mbx: mailbox.Mailbox, mail: Message | str) -> str | None:
        """
        stores given mail in mailbox. If mailbox is maildir, set the S-flag and
        return path to newly added mail. Oherwise this will return `None`.

        :param mbx: mailbox to use
        :param mail: the mail to store
        :returns: absolute path of mail-file for Maildir or None if mail was
                  successfully stored
        :raises: StoreMailError
        """
        if not isinstance(mbx, mailbox.Mailbox):
            logging.debug('Not a mailbox')
            return None

        mbx.lock()
        msg: mailbox.Message
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
            logging.debug('got mailbox msg id : %s', message_id)
        except Exception as e:
            raise StoreMailError(e)

        path = None
        # add new Maildir message to index and add tags
        if isinstance(mbx, mailbox.Maildir):
            # this is a dirty hack to get the path to the newly added file
            # I wish the mailbox module were more helpful...
            plist = glob.glob(os.path.join(mbx._path, 'new', message_id + '*'))
            if plist:
                path = plist[0]
                logging.debug('path of saved msg: %s', path)
        return path

    def store_sent_mail(self, mail: Message | str) -> str | None:
        """
        stores mail (:class:`email.message.Message` or str) in send-store if
        :attr:`sent_box` is set.
        """
        if self.sent_box is not None:
            return self.store_mail(self.sent_box, mail)
        return None

    def store_draft_mail(self, mail: Message | str) -> str | None:
        """
        stores mail (:class:`email.message.Message` or str) as draft if
        :attr:`draft_box` is set.
        """
        if self.draft_box is not None:
            return self.store_mail(self.draft_box, mail)
        return None

    async def send_mail(self, mail: Message | str) -> None:
        """
        sends given mail

        :param mail: the mail to send
        :raises SendingMailFailed: if sending fails
        """
        pass


class SendmailAccount(Account):
    """:class:`Account` that pipes a message to a `sendmail` shell command for
    sending"""

    def __init__(self, cmd: str, **kwargs: Any) -> None:
        """
        :param cmd: sendmail command to use for this account
        """
        super(SendmailAccount, self).__init__(**kwargs)
        self.cmd = cmd

    async def send_mail(self, mail: Message | str) -> None:
        """Pipe the given mail to the configured sendmail command.  Display a
        short message on success or a notification on error.
        :param mail: the mail to send out
        :raises: class:`SendingMailFailed` if sending failes
        """
        cmdlist = shlex.split(self.cmd)

        try:
            # make sure self.mail is a string
            out, err, code = await call_cmd_async(cmdlist, stdin=str(mail))
            if code != 0:
                msg = 'The sendmail command {} returned with code {}{}'.format(
                    self.cmd, code, ':\n' + err.strip() if err else '.')
                raise Exception(msg)
        except Exception as e:
            logging.error(str(e))
            raise SendingMailFailed(str(e))
        logging.info('sent mail successfully')
        logging.info(out)
