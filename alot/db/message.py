# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import email
import email.charset as charset
import email.policy
import functools
from datetime import datetime

from notmuch2 import NullPointerError

from . import utils
from .utils import get_body_part, extract_body_part
from .utils import decode_header
from .attachment import Attachment
from .. import helper
from ..settings.const import settings

charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')


@functools.total_ordering
class Message:
    """
    a persistent notmuch message object.
    It it uses a :class:`~alot.db.DBManager` for cached manipulation
    and lazy lookups.
    """
    def __init__(self, dbman, msg, thread=None):
        """
        :param dbman: db manager that is used for further lookups
        :type dbman: alot.db.DBManager
        :param msg: the wrapped message
        :type msg: notmuch2.Message
        :param thread: this messages thread (will be looked up later if `None`)
        :type thread: :class:`~alot.db.Thread` or `None`
        """
        self._dbman = dbman
        self._id = msg.messageid
        self._thread_id = msg.threadid
        self._thread = thread
        try:
            self._datetime = datetime.fromtimestamp(msg.date)
        except ValueError:
            self._datetime = None
        self._filename = str(msg.path)
        self._email = None  # will be read upon first use
        self._attachments = None  # will be read upon first use
        self._mime_part = None  # will be read upon first use
        self._mime_tree = None  # will be read upon first use
        self._tags = msg.tags

        self._session_keys = [
            value for _, value in msg.properties.getall(prefix="session-key",
                                                        exact=True)
        ]

        try:
            sender = decode_header(msg.header('From'))
            if not sender:
                sender = decode_header(msg.header('Sender'))
        except (NullPointerError, LookupError):
            sender = None
        if sender:
            self._from = sender
        elif 'draft' in self._tags:
            acc = settings.get_accounts()[0]
            self._from = '"{}" <{}>'.format(acc.realname, str(acc.address))
        else:
            self._from = '"Unknown" <>'
        try:
            self._subject = decode_header(msg.header('Subject'))
        except (NullPointerError, LookupError):
            self._subject = ''

    def __str__(self):
        """prettyprint the message"""
        aname, aaddress = self.get_author()
        if not aname:
            aname = aaddress
        return "%s (%s)" % (aname, self.get_datestring())

    def __hash__(self):
        """needed for sets of Messages"""
        return hash(self._id)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self._id == other.get_message_id()
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, type(self)):
            return self._id != other.get_message_id()
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, type(self)):
            return self._id < other.get_message_id()
        return NotImplemented

    def get_email(self):
        """returns :class:`email.email.EmailMessage` for this message"""
        path = self.get_filename()
        warning = "Subject: Caution!\n"\
                  "Message file is no longer accessible:\n%s" % path
        if not self._email:
            try:
                with open(path, 'rb') as f:
                    self._email = utils.decrypted_message_from_bytes(
                            f.read(), self._session_keys)
            except IOError:
                self._email = email.message_from_string(
                    warning, policy=email.policy.SMTP)
        return self._email

    def get_date(self):
        """returns Date header value as :class:`~datetime.datetime`"""
        return self._datetime

    def get_filename(self):
        """returns absolute path of message files location"""
        return self._filename

    def get_message_id(self):
        """returns messages id (str)"""
        return self._id

    def get_thread_id(self):
        """returns id (str) of the thread this message belongs to"""
        return self._thread_id

    def get_message_parts(self):
        """yield all body parts of this message"""
        for msg in self.get_email().walk():
            if not msg.is_multipart():
                yield msg

    def get_subject(self):
        return self._subject

    def get_tags(self):
        """returns tags attached to this message as list of strings"""
        return sorted(self._tags)

    def get_thread(self):
        """returns the :class:`~alot.db.Thread` this msg belongs to"""
        if not self._thread:
            self._thread = self._dbman.get_thread(self._thread_id)
        return self._thread

    def has_replies(self):
        """returns true if this message has at least one reply"""
        return len(self.get_replies()) > 0

    def get_replies(self):
        """returns replies to this message as list of :class:`Message`"""
        t = self.get_thread()
        return t.get_replies_to(self)

    def get_datestring(self):
        """
        returns reformated datestring for this message.

        It uses :meth:`SettingsManager.represent_datetime` to represent
        this messages `Date` header

        :rtype: str
        """
        if self._datetime is None:
            res = None
        else:
            res = settings.represent_datetime(self._datetime)
        return res

    def get_author(self):
        """
        returns realname and address of this messages author

        :rtype: (str,str)
        """
        return email.utils.parseaddr(self._from)

    def add_tags(self, tags, afterwards=None, remove_rest=False):
        """
        adds tags to message

        .. note::

            This only adds the requested operation to this objects
            :class:`DBManager's <alot.db.DBManager>` write queue.
            You need to call :meth:`~alot.db.DBManager.flush` to write out.

        :param tags: a list of tags to be added
        :type tags: list of str
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :type afterwards: callable
        :param remove_rest: remove all other tags
        :type remove_rest: bool
        """
        def myafterwards():
            if remove_rest:
                self._tags = set(tags)
            else:
                self._tags = self._tags.union(tags)
            if callable(afterwards):
                afterwards()

        self._dbman.tag('id:' + self._id, tags, afterwards=myafterwards,
                        remove_rest=remove_rest)
        self._tags = self._tags.union(tags)

    def remove_tags(self, tags, afterwards=None):
        """remove tags from message

        .. note::

            This only adds the requested operation to this objects
            :class:`DBManager's <alot.db.DBManager>` write queue.
            You need to call :meth:`~alot.db.DBManager.flush` to actually out.

        :param tags: a list of tags to be added
        :type tags: list of str
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :type afterwards: callable
        """
        def myafterwards():
            self._tags = self._tags.difference(tags)
            if callable(afterwards):
                afterwards()

        self._dbman.untag('id:' + self._id, tags, myafterwards)

    def get_attachments(self):
        """
        returns messages attachments

        Derived from the leaves of the email mime tree
        that and are not part of :rfc:`2015` syntax for encrypted/signed mails
        and either have :mailheader:`Content-Disposition` `attachment`
        or have :mailheader:`Content-Disposition` `inline` but specify
        a filename (as parameter to `Content-Disposition`).

        :rtype: list of :class:`Attachment`
        """
        if not self._attachments:
            self._attachments = []
            for part in self.get_message_parts():
                ct = part.get_content_type()
                # replace underspecified mime description by a better guess
                if ct in ['octet/stream', 'application/octet-stream']:
                    content = part.get_payload(decode=True)
                    ct = helper.guess_mimetype(content)
                    if (self._attachments and
                            self._attachments[-1].get_content_type() ==
                            'application/pgp-encrypted'):
                        self._attachments.pop()

                if self._is_attachment(part, ct):
                    self._attachments.append(Attachment(part))
        return self._attachments

    @staticmethod
    def _is_attachment(part, ct_override=None):
        """Takes a mimepart and returns a bool indicating if it's an attachment

        Takes an optional argument to override the content type.
        """
        cd = part.get('Content-Disposition', '')
        filename = part.get_filename()
        ct = ct_override or part.get_content_type()

        if cd.lower().startswith('attachment'):
            if ct.lower() not in ['application/pgp-signature']:
                return True
        elif cd.lower().startswith('inline'):
            if (filename is not None and ct.lower() != 'application/pgp'):
                return True

        return False

    def get_mime_part(self):
        if not self._mime_part:
            self._mime_part = get_body_part(self.get_email())
        return self._mime_part

    def set_mime_part(self, mime_part):
        self._mime_part = mime_part

    def get_body_text(self):
        """ returns bodystring extracted from this mail """
        return extract_body_part(self.get_mime_part())

    def matches(self, querystring):
        """tests if this messages is in the resultset for `querystring`"""
        searchfor = '( {} ) AND id:{}'.format(querystring, self._id)
        return self._dbman.count_messages(searchfor) > 0

    def get_mime_tree(self):
        if not self._mime_tree:
            self._mime_tree = self._get_mimetree(self.get_email())
        return self._mime_tree

    @classmethod
    def _get_mimetree(cls, message):
        label = cls._get_mime_part_info(message)
        if message.is_multipart():
            return label, [cls._get_mimetree(m) for m in message.get_payload()]
        else:
            if cls._is_attachment(message):
                message = Attachment(message)
            return label, message

    @staticmethod
    def _get_mime_part_info(mime_part):
        contenttype = mime_part.get_content_type()
        filename = mime_part.get_filename() or '(no filename)'
        charset = mime_part.get_content_charset() or ''
        size = helper.humanize_size(len(mime_part.as_string()))
        return ' '.join((contenttype, filename, charset, size))
