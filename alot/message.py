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


class Message:
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
        # TODO: change api to return unicode
        self._from = msg.get_header('From')
        self._email = None  # will be read upon first use
        self._attachments = None  # will be read upon first use
        self._tags = set(msg.get_tags())

    def __str__(self):
        """prettyprint the message"""
        aname, aaddress = self.get_author()
        if not aname:
            aname = aaddress
        #tags = ','.join(self.get_tags())
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

    def get_datestring(self, pretty=True):
        """returns formated datestring in sup-style, eg: 'Yest.3pm'"""
        return helper.pretty_datetime(self._datetime)

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
            ctype = part.get_content_type()
            enc = part.get_content_charset()
            if part.get_content_maintype() == 'text':
                raw_payload = part.get_payload(decode=True)
                if enc:
                    raw_payload = raw_payload.decode(enc, errors='replace')
                else:
                    raw_payload = unicode(raw_payload, errors='replace')
                res += raw_payload
        return res


def extract_body(mail):
    bodytxt = ''
    for part in mail.walk():
        ctype = part.get_content_type()
        enc = part.get_content_charset()
        raw_payload = part.get_payload(decode=True)
        if part.get_content_maintype() == 'text':
            if enc:
                raw_payload = unicode(raw_payload, enc)
            else:
                raw_payload = unicode(raw_payload, errors='replace')
        if ctype == 'text/plain':
            bodytxt += raw_payload
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
                #create and call external command
                cmd = handler % tmpfile.name
                rendered_payload = helper.cmd_output(cmd)
                #remove tempfile
                tmpfile.close()
                os.unlink(tmpfile.name)
                if rendered_payload:  # handler had output
                    bodytxt += unicode(rendered_payload.strip(),
                                       encoding='utf8', errors='replace')
                elif part.get_content_maintype() == 'text':
                    bodytxt += raw_payload
                # else drop
    return bodytxt


def decode_to_unicode(part):
    enc = part.get_content_charset()
    raw_payload = part.get_payload(decode=True)
    if enc:
        raw_payload = unicode(raw_payload, enc)
    else:
        raw_payload = unicode(raw_payload, errors='replace')
    return raw_payload


def decode_header(header):
    valuelist = email.header.decode_header(header)
    value = u''
    for v, enc in valuelist:
        if enc:
            value = value + v.decode(enc)
        else:
            value = value + v
    value = value.replace('\r', '')
    value = value.replace('\n', ' ')
    return value


def encode_header(key, value):
    if key.lower() in ['from', 'to', 'cc', 'bcc']:
        rawentries = value.split(',')
        encodedentries = []
        for entry in rawentries:
            m = re.search('\s*(.*)\s+<(.*\@.*\.\w*)>$', entry)
            if m:
                name, address = m.groups()
                header = Header(name + ' ', 'utf-8')
                header.append('<%s>' % address, charset='ascii')
                encodedentries.append(header.encode())
            else:
                encodedentries.append(entry.encode('ascii', errors='replace'))
        value = Header(','.join(encodedentries))
    elif key.lower() == 'subject':
        value = Header(value, 'UTF-8')
    else:
        value = Header(value.encode('ascii', errors='replace'))
    return value


class Attachment:
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
                               self.get_size())

    def get_filename(self):
        """return the filename, extracted from content-disposition header"""
        return self.part.get_filename()

    def get_content_type(self):
        """mime type of the attachment"""
        ctype = self.part.get_content_type()
        if ctype == 'octet/stream' and self.get_filename():
            ctype, enc = mimetypes.guess_type(self.get_filename())
        return ctype

    def get_size(self):
        """returns attachments size as human-readable string"""
        size_in_kbyte = len(self.part.get_payload()) / 1024
        if size_in_kbyte > 1024:
            return "%.1fM" % (size_in_kbyte / 1024.0)
        else:
            return "%dK" % size_in_kbyte

    def save(self, path):
        """save the attachment to disk. Uses self.get_filename
        in case path is a directory"""
        if self.get_filename() and os.path.isdir(path):
            path = os.path.join(path, self.get_filename())
            FILE = open(path, "w")
        else:
            FILE = tempfile.NamedTemporaryFile(delete=False)
        FILE.write(self.part.get_payload(decode=True))
        FILE.close()
        return FILE.name
