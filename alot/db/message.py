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
        self._attachments = []  # will be read upon first use
        self._inlines = []  # stores inline parts
        self._tags = set(msg.get_tags())

    def read_mail(self):
        self._attachments = []
        self._inlines = []
        self._read_part(self.get_email())

    def _add_attachment(self, a):
        logging.debug('add attachment: %s' % a.get_content_type())
        self._attachments.append(Attachment(a))

    def _read_part(self, part):
        ctype = part.get_content_type()
        maintype = part.get_content_maintype()
        subtype = part.get_content_subtype()
        cdisp = part.get('Content-Disposition', '')
        logging.debug('read part: %s' % ctype)

        if maintype == 'text':
            logging.debug('text')
            if cdisp.startswith('attachment'):
                self._add_attachment(part)
            else:
                content = helper.read_text_part(part)
                if subtype == 'html':
                    content = helper.tidy_html(content)
                logging.debug('add inline')
                self._inlines.append((ctype, content, None))

        elif ctype == 'message/rfc822':
            logging.debug('rfc822')
            # A message/rfc822 part contains an email message, including any
            # headers. This is used for digests as well as for email
            # forwarding. Defined in RFC 2046.

            # TODO: use extract_headers to get text representation of the
            # headers (filter interesting to ones via config setting) add this
            # string to self._inlines and continue recursively with
            self._add_attachment(part)

        elif ctype == 'multipart/mixed':
            logging.debug('multipart/mixed. rucurring')
            # Multipart/mixed is used for sending files with different
            # "Content-Type" headers inline (or as attachments). Defined in RFC
            # 2046, Section 5.1.3
            for subpart in part.get_payload():
                self._read_part(subpart)
        elif ctype == 'multipart/digest':
            # Multipart/digest is a simple way to send multiple text messages.
            # The default content-type for each part is "message/rfc822".
            # Defined in RFC 2046, Section 5.1.5
            # TODO
            pass
        elif ctype == 'multipart/alternative':
            # The multipart/alternative subtype indicates that each part is an
            # "alternative" version of the same (or similar) content, each in a
            # different format denoted by its "Content-Type" header. The formats
            # are ordered by how faithful they are to the original, with the
            # least faithful first and the most faithful last.

            # This structure places the plain text version (if present) first.

            # Most commonly, multipart/alternative is used for email with two
            # parts, one plain text (text/plain) and one HTML (text/html).

            # Defined in RFC 2046, Section 5.1.4

            alternative = None
            for subpart in part.get_payload():
                if subpart.get_content_type() == 'text/plain':
                    alternative = helper.read_text_part(subpart)
                elif subpart.get_content_type() == 'text/html':
                    content = helper.tidy_html(helper.read_text_part(subpart))
                else:
                    content = part.get_payload(decode=True)
            self._inlines.append((ctype, content, None))

        elif ctype == 'multipart/related':
            # A multipart/related is used to indicate that each message part is
            # a component of an aggregate whole. It is for compound objects
            # consisting of several inter-related components - proper display
            # cannot be achieved by individually displaying the constituent
            # parts. The message consists of a root part (by default, the first)
            # which reference other parts inline, which may in turn reference
            # other parts. Message parts are commonly referenced by the
            # "Content-ID" part header. The syntax of a reference is unspecified
            # and is instead dictated by the encoding or protocol used in the
            # part.
            #
            # One common usage of this subtype is to send a web page complete
            # with images in a single message. The root part would contain the
            # HTML document, and use image tags to reference images stored in
            # the latter parts.
            #
            # Defined in RFC 2387
            # TODO
            pass

        elif ctype == 'multipart/report':
            # Multipart/report is a message type that contains data formatted
            # for a mail server to read. It is split between a text/plain (or
            # some other content/type easily readable) and a
            # message/delivery-status, which contains the data formatted for the
            # mail server to read.  Defined in RFC 6522
            # TODO
            pass
        elif ctype == 'multipart/signed':
            # A multipart/signed message is used to attach a digital signature
            # to a message.  It has two parts, a body part and a signature part.
            # The whole of the body part, including mime headers, is used to
            # create the signature part. Many signature types are possible, like
            # application/pgp-signature (RFC 3156) and
            # application/pkcs7-signature (S/MIME).  Defined in RFC 1847,
            # Section 2.1
            # TODO
            pass
        elif ctype == 'multipart/encrypted':
            # A multipart/encrypted message has two parts. The first part has
            # control information that is needed to decrypt the
            # application/octet-stream second part. Similar to signed messages,
            # there are different implementations which are identified by their
            # separate content types for the control part. The most common types
            # are "application/pgp-encrypted" (RFC 3156) and
            # "application/pkcs7-mime" (S/MIME).  Defined in RFC 1847, Section
            # 2.2
            # TODO
            pass
        elif ctype == 'multipart/form-data':
            # As its name implies, multipart/form-data is used to express values
            # submitted through a form. Originally defined as part of HTML 4.0,
            # it is most commonly used for submitting files via HTTP.  Defined
            # in RFC 2388
            # TODO
            pass
        elif ctype == 'multipart/x-mixed-replace':
            # The content type multipart/x-mixed-replace was developed as part
            # of a technology to emulate server push and streaming over HTTP.
            # TODO
            pass
        elif ctype == 'multipart/byteranges':
            # The multipart/byteranges is used to represent noncontiguous byte
            # ranges of a single message. It is used by HTTP when a server
            # returns multiple byte ranges and is defined in RFC 2616.
            # TODO
            pass
        else:  # catchall: try to handle inline if requested, otherwise attach
            logging.debug('catchall: %s' % cdisp)
            if cdisp == 'inline':
                content = part.get_payload(decode=True)
                alt_text = '[%s part]' % ctype
                logging.debug('add inline')
                self._inlines.append((ctype, content, alt_text))
            else:
                self._add_attachment(part)
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
            return None
        formatstring = settings.get('timestamp_format')
        if formatstring == None:
            res = helper.pretty_datetime(self._datetime)
        else:
            res = self._datetime.strftime(formatstring)
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
        return extract_headers(self.get_mail(), headers)

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
