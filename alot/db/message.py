import email
from datetime import datetime
import email.charset as charset
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')
from notmuch import NullPointerError

import alot.helper as helper
from alot.settings import settings

from utils import extract_headers, extract_body
from attachment import Attachment


class Message(object):
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
        :type msg: notmuch.database.Message
        :param thread: this messages thread (will be looked up later if `None`)
        :type thread: :class:`~alot.db.Thread` or `None`
        """
        self._dbman = dbman
        self._id = msg.get_message_id()
        self._thread_id = msg.get_thread_id()
        self._thread = thread
        casts_date = lambda: datetime.fromtimestamp(msg.get_date())
        self._datetime = helper.safely_get(casts_date,
                                          ValueError, None)
        self._filename = msg.get_filename()
        self._from = helper.safely_get(lambda: msg.get_header('From'),
                                       NullPointerError)
        self._email = None  # will be read upon first use
        self._attachments = None  # will be read upon first use
        self._tags = set(msg.get_tags())

    def __str__(self):
        """prettyprint the message"""
        aname, aaddress = self.get_author()
        if not aname:
            aname = aaddress
        return "%s (%s)" % (aname, self.get_datestring())

    def __hash__(self):
        """needed for sets of Messages"""
        return hash(self._id)

    def __cmp__(self, other):
        """needed for Message comparison"""
        res = cmp(self.get_message_id(), other.get_message_id())
        return res

    def get_email(self):
        """returns :class:`email.Message` for this message"""
        path = self.get_filename()
        warning = "Subject: Caution!\n"\
                  "Message file is no longer accessible:\n%s" % path
        if not self._email:
            try:
                f_mail = open(path)
                self._email = email.message_from_file(f_mail)
                f_mail.close()
            except IOError:
                self._email = email.message_from_string(warning)
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
        """returns a list of all body parts of this message"""
        # TODO really needed? email  iterators can do this
        out = []
        for msg in self.get_email().walk():
            if not msg.is_multipart():
                out.append(msg)
        return out

    def get_tags(self):
        """returns tags attached to this message as list of strings"""
        l = list(self._tags)
        l.sort()
        return l

    def get_thread(self):
        """returns the :class:`~alot.db.Thread` this msg belongs to"""
        if not self._thread:
            self._thread = self._dbman.get_thread(self._thread_id)
        return self._thread

    def has_replies(self):
        """returns true if this message has at least one reply"""
        return (len(self.get_replies()) > 0)

    def get_replies(self):
        """returns replies to this message as list of :class:`Message`"""
        t = self.get_thread()
        return t.get_replies_to(self)

    def get_datestring(self):
        """
        returns reformated datestring for this messages.

        It uses the format spacified by `timestamp_format` in
        the general section of the config.
        """
        if self._datetime == None:
            res = None
        else:
            res = settings.represent_datetime(self._datetime)
        return res

    def get_author(self):
        """
        returns realname and address of this messages author

        :rtype: (str,str)
        """
        return email.Utils.parseaddr(self._from)

    def get_headers_string(self, headers):
        """
        returns subset of this messages headers as human-readable format:
        all header values are decoded, the resulting string has
        one line "KEY: VALUE" for each requested header present in the mail.

        :param headers: headers to extract
        :type headers: list of str
        """
        return extract_headers(self.get_email(), headers)

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
                cd = part.get('Content-Disposition', '')
                filename = part.get_filename()
                ct = part.get_content_type()
                # replace underspecified mime description by a better guess
                if ct in ['octet/stream', 'application/octet-stream']:
                    content = part.get_payload(decode=True)
                    ct = helper.guess_mimetype(content)

                if cd.startswith('attachment'):
                    if ct not in ['application/pgp-encrypted',
                                  'application/pgp-signature']:
                        self._attachments.append(Attachment(part))
                elif cd.startswith('inline'):
                    if filename != None and ct != 'application/pgp':
                        self._attachments.append(Attachment(part))
        return self._attachments

    def accumulate_body(self):
        """
        returns bodystring extracted from this mail
        """
        #TODO: don't hardcode which part is considered body but allow toggle
        #      commands and a config default setting

        return extract_body(self.get_email())

    def get_text_content(self):
        return extract_body(self.get_email(), types=['text/plain'])

    def matches(self, querystring):
        """tests if this messages is in the resultset for `querystring`"""
        searchfor = querystring + ' AND id:' + self._id
        return self._dbman.count_messages(searchfor) > 0
