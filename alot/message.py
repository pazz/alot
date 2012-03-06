import os
import email
import tempfile
import re
import shlex
from datetime import datetime
from email.header import Header
import email.charset as charset
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')
from email.iterators import typed_subpart_iterator
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from notmuch import NullPointerError

from alot import __version__
import logging
import helper
from settings import settings
from helper import string_sanitize
from helper import string_decode


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


def extract_headers(mail, headers=None):
    headertext = u''
    if headers == None:
        headers = mail.keys()
    for key in headers:
        value = u''
        if key in mail:
            value = decode_header(mail.get(key, ''))
        headertext += '%s: %s\n' % (key, value)
    return headertext


def extract_body(mail, types=None):
    """
    returns a body text string for given mail.
    If types is `None`, 'text/*' is used:
    In case mail has a 'text/html' part, it is prefered over
    'text/plain' parts.

    :param mail: the mail to use
    :type mail: :class:`email.Message`
    :param types: mime content types to use for body string
    :type types: list of str
    """
    html = list(typed_subpart_iterator(mail, 'text', 'html'))

    # if no specific types are given, we favor text/html over text/plain
    drop_plaintext = False
    if html and not types:
        drop_plaintext = True

    body_parts = []
    for part in mail.walk():
        ctype = part.get_content_type()

        if types is not None:
            if ctype not in types:
                continue
        cd = part.get('Content-Disposition', '')
        if cd.startswith('attachment'):
            continue

        enc = part.get_content_charset() or 'ascii'
        raw_payload = part.get_payload(decode=True)
        if part.get_content_maintype() == 'text':
            raw_payload = string_decode(raw_payload, enc)
        if ctype == 'text/plain' and not drop_plaintext:
            body_parts.append(string_sanitize(raw_payload))
        else:
            #get mime handler
            handler = settings.get_mime_handler(ctype, key='view',
                                                interactive=False)
            if handler:
                #open tempfile. Not all handlers accept stuff from stdin
                tmpfile = tempfile.NamedTemporaryFile(delete=False,
                                                      suffix='.html')
                #write payload to tmpfile
                if part.get_content_maintype() == 'text':
                    tmpfile.write(raw_payload.encode('utf8'))
                else:
                    tmpfile.write(raw_payload)
                tmpfile.close()
                #create and call external command
                cmd = handler % tmpfile.name
                cmdlist = shlex.split(cmd.encode('utf-8', errors='ignore'))
                rendered_payload, errmsg, retval = helper.call_cmd(cmdlist)
                #remove tempfile
                os.unlink(tmpfile.name)
                if rendered_payload:  # handler had output
                    body_parts.append(string_sanitize(rendered_payload))
                elif part.get_content_maintype() == 'text':
                    body_parts.append(string_sanitize(raw_payload))
                # else drop
    return '\n\n'.join(body_parts)


def decode_header(header, normalize=False):
    """
    decode a header value to a unicode string

    values are usually a mixture of different substrings
    encoded in quoted printable using diffetrent encodings.
    This turns it into a single unicode string

    :param header: the header value
    :type header: str in us-ascii
    :param normalize: replace trailing spaces after newlines
    :type normalize: bool
    :rtype: unicode
    """

    valuelist = email.header.decode_header(header)
    decoded_list = []
    for v, enc in valuelist:
        v = string_decode(v, enc)
        decoded_list.append(string_sanitize(v))
    value = u' '.join(decoded_list)
    if normalize:
        value = re.sub(r'\n\s+', r' ', value)
    return value


def encode_header(key, value):
    """
    encodes a unicode string as a valid header value

    :param key: the header field this value will be stored in
    :type key: str
    :param value: the value to be encoded
    :type value: unicode
    """
    # handle list of "realname <email>" entries separately
    if key.lower() in ['from', 'to', 'cc', 'bcc']:
        rawentries = value.split(',')
        encodedentries = []
        for entry in rawentries:
            m = re.search('\s*(.*)\s+<(.*\@.*\.\w*)>\s*$', entry)
            if m:  # If a realname part is contained
                name, address = m.groups()
                # try to encode as ascii, if that fails, revert to utf-8
                # name must be a unicode string here
                namepart = Header(name)
                # append address part encoded as ascii
                entry = '%s <%s>' % (namepart.encode(), address)
            encodedentries.append(entry)
        value = Header(', '.join(encodedentries))
    else:
        value = Header(value)
    return value


class Attachment(object):
    """represents a mail attachment"""

    def __init__(self, emailpart):
        """
        :param emailpart: a non-multipart email that is the attachment
        :type emailpart: :class:`email.message.Message`
        """
        self.part = emailpart

    def __str__(self):
        desc = '%s:%s (%s)' % (self.get_content_type(),
                              self.get_filename(),
                              helper.humanize_size(self.get_size()))
        return string_decode(desc)

    def get_filename(self):
        """
        return name of attached file.
        If the content-disposition header contains no file name,
        this returns `None`
        """
        extracted_name = decode_header(self.part.get_filename())
        if extracted_name:
            return os.path.basename(extracted_name)
        return None

    def get_content_type(self):
        """mime type of the attachment part"""
        ctype = self.part.get_content_type()
        # replace underspecified mime description by a better guess
        if ctype in ['octet/stream', 'application/octet-stream']:
            ctype = helper.guess_mimetype(self.get_data())
        return ctype

    def get_size(self):
        """returns attachments size in bytes"""
        return len(self.part.get_payload())

    def save(self, path):
        """
        save the attachment to disk. Uses :meth:`get_filename` in case path
        is a directory
        """
        filename = self.get_filename()
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            if filename:
                basename = os.path.basename(filename)
                FILE = open(os.path.join(path, basename), "w")
            else:
                FILE = tempfile.NamedTemporaryFile(delete=False, dir=path)
        else:
            FILE = open(path, "w")  # this throws IOErrors for invalid path
        FILE.write(self.get_data())
        FILE.close()
        return FILE.name

    def get_data(self):
        """return data blob from wrapped file"""
        return self.part.get_payload(decode=True)

    def get_mime_representation(self):
        """returns mime part that constitutes this attachment"""
        return self.part


class Envelope(object):
    """a message that is not yet sent and still editable"""
    def __init__(self, template=None, bodytext=u'', headers={}, attachments=[],
            sign=False, encrypt=False):
        """
        :param template: if not None, the envelope will be initialised by
                         :meth:`parsing <parse_template>` this string before
                         setting any other values given to this constructor.
        :type template: str
        :param bodytext: text used as body part
        :type bodytext: str
        :param headers: unencoded header values
        :type headers: dict (str -> unicode)
        :param attachments: file attachments to include
        :type attachments: list of :class:`Attachment`
        """
        assert isinstance(bodytext, unicode)
        self.headers = {}
        self.body = None
        logging.debug('TEMPLATE: %s' % template)
        if template:
            self.parse_template(template)
            logging.debug('PARSED TEMPLATE: %s' % template)
            logging.debug('BODY: %s' % self.body)
        if self.body == None:
            self.body = bodytext
        self.headers.update(headers)
        self.attachments = list(attachments)
        self.sign = sign
        self.encrypt = encrypt
        self.sent_time = None
        self.modified_since_sent = False

    def __str__(self):
        return "Envelope (%s)\n%s" % (self.headers, self.body)

    def __setitem__(self, name, val):
        """setter for header values. this allows adding header like so:

        >>> envelope['Subject'] = u'sm\xf8rebr\xf8d'
        """
        self.headers[name] = val

        if self.sent_time:
            self.modified_since_sent = True

    def __getitem__(self, name):
        """getter for header values.
        :raises: KeyError if undefined
        """
        return self.headers[name]

    def __delitem__(self, name):
        del(self.headers[name])

        if self.sent_time:
            self.modified_since_sent = True

    def __contains__(self, name):
        return self.headers.__contains__(name)

    def get(self, key, fallback=None):
        """secure getter for header values that allows specifying a `fallback`
        return string (defaults to None). This returns the first matching value
        and doesn't raise KeyErrors"""
        if key in self.headers:
            value = self.headers[key][0]
        else:
            value = fallback
        return value

    def get_all(self, key, fallback=[]):
        """returns all header values for given key"""
        if key in self.headers:
            value = self.headers[key]
        else:
            value = fallback
        return value

    def add(self, key, value):
        """add header value"""
        if key not in self.headers:
            self.headers[key] = []
        self.headers[key].append(value)

        if self.sent_time:
            self.modified_since_sent = True

    def attach(self, attachment, filename=None, ctype=None):
        """
        attach a file

        :param attachment: File to attach, given as :class:`Attachment` object
                           or path to a file.
        :type attachment: :class:`Attachment` or str
        :param filename: filename to use in content-disposition.
                         Will be ignored if `path` matches multiple files
        :param ctype: force content-type to be used for this attachment
        :type ctype: str
        """

        if isinstance(attachment, Attachment):
            self.attachments.append(attachment)
        elif isinstance(attachment, basestring):
            path = os.path.expanduser(attachment)
            part = helper.mimewrap(path, filename, ctype)
            self.attachments.append(Attachment(part))
        else:
            raise TypeError('attach accepts an Attachment or str')

        if self.sent_time:
            self.modified_since_sent = True

    def construct_mail(self):
        """
        compiles the information contained in this envelope into a
        :class:`email.Message`.
        """
        # build body text part
        textpart = MIMEText(self.body.encode('utf-8'), 'plain', 'utf-8')

        # wrap it in a multipart container if necessary
        if self.attachments or self.sign or self.encrypt:
            msg = MIMEMultipart()
            msg.attach(textpart)
        else:
            msg = textpart

        headers = self.headers.copy()
        # add Message-ID
        if 'Message-ID' not in headers:
            headers['Message-ID'] = [email.Utils.make_msgid()]

        if 'User-Agent' in headers:
            uastring_format = headers['User-Agent'][0]
        else:
            uastring_format = settings.get('user_agent').strip()
        uastring = uastring_format.format(version=__version__)
        if uastring:
            headers['User-Agent'] = [uastring]

        # copy headers from envelope to mail
        for k, vlist in headers.items():
            for v in vlist:
                msg[k] = encode_header(k, v)

        # add attachments
        for a in self.attachments:
            msg.attach(a.get_mime_representation())

        return msg

    def parse_template(self, tmp, reset=False, only_body=False):
        """parses a template or user edited string to fills this envelope.

        :param tmp: the string to parse.
        :type tmp: str
        :param reset: remove previous envelope content
        :type reset: bool
        """
        logging.debug('GoT: """\n%s\n"""' % tmp)

        if self.sent_time:
            self.modified_since_sent = True

        if only_body:
            self.body = tmp
        else:
            m = re.match('(?P<h>([a-zA-Z0-9_-]+:.+\n)*)\n?(?P<b>(\s*.*)*)', tmp)
            assert m

            d = m.groupdict()
            headertext = d['h']
            self.body = d['b']

            # remove existing content
            if reset:
                self.headers = {}

            # go through multiline, utf-8 encoded headers
            # we decode the edited text ourselves here as
            # email.message_from_file can't deal with raw utf8 header values
            key = value = None
            for line in headertext.splitlines():
                if re.match('[a-zA-Z0-9_-]+:', line):  # new k/v pair
                    if key and value:  # save old one from stack
                        self.add(key, value)  # save
                    key, value = line.strip().split(':', 1)  # parse new pair
                elif key and value:  # append new line without key prefix
                    value += line
            if key and value:  # save last one if present
                self.add(key, value)
