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
import os
import email
import tempfile
import re
import mimetypes
from datetime import datetime
from email.header import Header

import helper
from settings import get_mime_handler
from settings import config


class Message(object):
    def __init__(self, dbman, msg, thread=None):
        """
        :param dbman: db manager that is used for further lookups
        :type dbman: alot.db.DBManager
        :param msg: the wrapped message
        :type msg: notmuch.database.Message
        :param thread: this messages thread
        :type thread: alot.db.thread
        """
        self._dbman = dbman
        self._id = msg.get_message_id()
        self._thread_id = msg.get_thread_id()
        self._thread = thread
        self._datetime = datetime.fromtimestamp(msg.get_date())
        self._filename = msg.get_filename()
        self._from = msg.get_header('From')
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
        """Implement hash(), so we can use Message() sets"""
        return hash(self._id)

    def __cmp__(self, other):
        """Implement cmp(), so we can compare Message()s"""
        res = cmp(self.get_message_id(), other.get_message_id())
        return res

    def get_email(self):
        """returns email.Message representing this message"""
        if not self._email:
            f_mail = open(self.get_filename())
            self._email = email.message_from_file(f_mail)
            f_mail.close()
        return self._email

    def get_date(self):
        """returns date as datetime obj"""
        return self._datetime

    def get_filename(self):
        """returns absolute path of messages location"""
        return self._filename

    def get_message_id(self):
        """returns messages id (a string)"""
        return self._id

    def get_thread_id(self):
        """returns id of messages thread (a string)"""
        return self._thread_id

    def get_message_parts(self):
        """returns a list of all body parts of this message"""
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
        """returns the thread this msg belongs to as alot.db.Thread object"""
        if not self._thread:
            self._thread = self._dbman.get_thread(self._thread_id)
        return self._thread

    def get_replies(self):
        """returns a list of replies to this msg"""
        t = self.get_thread()
        return t.get_replies_to(self)

    def get_datestring(self):
        """returns formated datestring"""
        formatstring = config.get('general', 'timestamp_format')
        if formatstring:
            res = self._datetime.strftime(formatstring)
        else:
            res = helper.pretty_datetime(self._datetime)
        return res

    def get_author(self):
        """returns realname and address pair of this messages author"""
        return email.Utils.parseaddr(self._from)

    def add_tags(self, tags):
        """adds tags to message

        :param tags: tags to add
        :type tags: list of str
        """
        self._dbman.tag('id:' + self._id, tags)
        self._tags = self._tags.union(tags)

    def remove_tags(self, tags):
        """remove tags from message

        :param tags: tags to remove
        :type tags: list of str
        """
        self._dbman.untag('id:' + self._id, tags)
        self._tags = self._tags.difference(tags)

    def get_attachments(self):
        if not self._attachments:
            self._attachments = []
            for part in self.get_message_parts():
                if part.get_content_maintype() != 'text':
                    self._attachments.append(Attachment(part))
        return self._attachments

    def accumulate_body(self):
        return extract_body(self.get_email())

    def matches(self, querystring):
        searchfor = querystring + ' AND id:' + self._id
        return self._dbman.count_messages(searchfor) > 0

    def get_text_content(self):
        res = ''
        for part in self.get_email().walk():
            enc = part.get_content_charset()
            if part.get_content_maintype() == 'text':
                raw_payload = part.get_payload(decode=True)
                if enc:
                    raw_payload = raw_payload.decode(enc, errors='replace')
                else:
                    raw_payload = unicode(raw_payload, errors='replace')
                res += raw_payload
        return res


def extract_body(mail, ignore_mimetypes):
    body_parts = []
    for part in mail.walk():
        ctype = part.get_content_type()
        if ctype in ignore_mimetypes:
            continue
        enc = part.get_content_charset()
        raw_payload = part.get_payload(decode=True)
        if part.get_content_maintype() == 'text':
            if enc:
                raw_payload = unicode(raw_payload, enc, errors='replace')
            else:
                raw_payload = unicode(raw_payload, errors='replace')
        if ctype == 'text/plain':
            body_parts.append(raw_payload)
        else:
            #get mime handler
            handler = get_mime_handler(ctype, key='view',
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
                rendered_payload = helper.cmd_output(cmd)
                #remove tempfile
                os.unlink(tmpfile.name)
                if rendered_payload:  # handler had output
                    body_parts.append(rendered_payload.strip())
                elif part.get_content_maintype() == 'text':
                    body_parts.append(raw_payload)
                # else drop
    return '\n\n'.join(body_parts)


def decode_to_unicode(part):
    enc = part.get_content_charset()
    raw_payload = part.get_payload(decode=True)
    if enc:
        raw_payload = unicode(raw_payload, enc)
    else:
        raw_payload = unicode(raw_payload, errors='replace')
    return raw_payload


def decode_header(header):
    """decode a header value to a unicode string

    values are usually a mixture of different substrings
    encoded in quoted printable using diffetrent encodings.
    This turns it into a single unicode string

    :param header: the header value
    :type header: str in us-ascii
    :rtype: unicode
    """

    valuelist = email.header.decode_header(header)
    decoded_list = []
    for v, enc in valuelist:
        if enc:
            decoded_list.append(v.decode(enc))
        else:
            decoded_list.append(v)
    return u' '.join(decoded_list)


def encode_header(key, value):
    """encodes a unicode string as a valid header value

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
            m = re.search('\s*(.*)\s+<(.*\@.*\.\w*)>$', entry)
            if m:  # If a realname part is contained
                name, address = m.groups()
                # try to encode as ascii, if that fails, revert to utf-8
                # name must be a unicode string here
                header = Header(name)
                # append address part encoded as ascii
                header.append('<%s>' % address, charset='ascii')
                encodedentries.append(header.encode())
            else:  # pure email address
                encodedentries.append(entry)
        value = Header(','.join(encodedentries))
    else:
        value = Header(value)
    return value


class Attachment(object):
    """represents a single mail attachment"""

    def __init__(self, emailpart):
        """
        :param emailpart: a non-multipart email that is the attachment
        :type emailpart: email.message.Message
        """
        self.part = emailpart

    def __str__(self):
        return '%s:%s (%s)' % (self.get_content_type(),
                               self.get_filename(),
                               helper.humanize_size(self.get_size()))

    def get_filename(self):
        """return the filename, extracted from content-disposition header"""
        extracted_name = self.part.get_filename()
        if extracted_name:
            return os.path.basename(extracted_name)
        return None

    def get_content_type(self):
        """mime type of the attachment"""
        ctype = self.part.get_content_type()
        if ctype == 'octet/stream' and self.get_filename():
            ctype, enc = mimetypes.guess_type(self.get_filename())
        return ctype
    def get_size(self):
        """returns attachments size in bytes"""
        return len(self.part.get_payload())

    def save(self, path):
        """save the attachment to disk. Uses self.get_filename
        in case path is a directory"""
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
        FILE.write(self.part.get_payload(decode=True))
        FILE.close()
        return FILE.name
