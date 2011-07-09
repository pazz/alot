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
from notmuch import Database, NotmuchError
from datetime import datetime
import email
from collections import deque
import os

from settings import config
import helper

DB_ENC = 'utf8'


class DBManager:
    """
    keeps track of your index parameters, can create notmuch.Query
    objects from its Database on demand and implements a bunch of
    database specific functions.
    """
    def __init__(self, path=None, ro=False):
        self.ro = ro
        self.path = path
        self.writequeue = deque([])

    def flush(self):
        """
        tries to flush all queued write commands to the index
        """
        if self.writequeue:
            try:
                mode = Database.MODE.READ_WRITE
                db = Database(path=self.path, mode=mode)
            except NotmuchError:
                if self.ui:  # let the mainloop call us again after timeout
                    timeout = config.getint('general', 'flush_retry_timeout')
                    self.ui.update()

                    def f(*args):
                        self.flush()
                    self.ui.mainloop.set_alarm_in(timeout, f)
                return
            while self.writequeue:
                cmd, querystring, tags = self.writequeue.popleft()
                query = db.create_query(querystring)
                for msg in query.search_messages():
                    msg.freeze()
                    if cmd == 'tag':
                        for tag in tags:
                            msg.add_tag(tag)
                    if cmd == 'set':
                        msg.remove_all_tags()
                        for tag in tags:
                            msg.add_tag(tag)
                    elif cmd == 'untag':
                        for tag in tags:
                            msg.remove_tag(tag)
                    msg.thaw()
            if self.ui:  # trigger status update
                self.ui.update()

    def tag(self, querystring, tags, remove_rest=False):
        """
        add tags to all matching messages

        :param querystring: notmuch search string
        :type querystring: str
        :param tags: a list of tags to be added
        :type tags: list of str
        :param remove_rest: remove tags from matching messages before tagging
        :type remove_rest: boolean
        """
        if remove_rest:
            self.writequeue.append(('set', querystring, tags))
        else:
            self.writequeue.append(('tag', querystring, tags))
        self.flush()

    def untag(self, querystring, tags):
        """
        add tags to all matching messages

        :param querystring: notmuch search string
        :type querystring: str
        :param tags: a list of tags to be added
        :type tags: list of str
        """
        self.writequeue.append(('untag', querystring, tags))
        self.flush()

    def count_messages(self, querystring):
        return self.query(querystring).count_messages()

    def search_thread_ids(self, querystring):
        threads = self.query(querystring).search_threads()
        return [thread.get_thread_id() for thread in threads]

    #def find_message(self, mid):
    #    db = Database(path=self.path)
    #    query = self.query('id:' + mid)
    #    try:
    #        thread = query.search_threads().next()
    #        def search_msg_in_replies(mid, msg):
    #            if msg.get_message_id() == mid:
    #                return msg
    #            else:
    #                replies = msg.get_replies()
    #                if replies is not None:
    #                    for r in replies:
    #                        return search_msg_in_replies(mid, r)

    #        for m in thread.get_toplevel_messages():
    #            return searchformsg(mid, msg)
    #    except:
    #        return None
    #        #TODO raise exceptions here in 0<case msgcount>1
    #        msg = query.search_messages().next()

    #def get_message(self, mid):
    #    """returns the message with the given id and wrapps it in a Message

    #    :param mid: the message id of the message to look up
    #    :type mid: str.
    #    :returns:  Message -- the message.

    #    """
    #    return Message(self, self.find_message(mid))

    def get_thread(self, tid):
        query = self.query('thread:' + tid)
        #TODO raise exceptions here in 0<case msgcount>1
        return Thread(self, query.search_threads().next())

    def get_all_tags(self):
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return [tag for tag in db.get_all_tags()]

    def query(self, querystring):
        """creates notmuch.Query objects on demand

        :param querystring: The query string to use for the lookup
        :type query: str.
        :returns:  notmuch.Query -- the query object.

        """
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return db.create_query(querystring.encode(DB_ENC))


class Thread:
    def __init__(self, dbman, thread):
        self.dbman = dbman
        self.tid = thread.get_thread_id()
        self.strrep = str(thread).decode(DB_ENC)
        self.total_messages = thread.get_total_messages()
        self.topmessages = [m.get_message_id() for m in thread.get_toplevel_messages()]
        self.authors = str(thread.get_authors()).decode(DB_ENC)
        self.subject = str(thread.get_subject()).decode(DB_ENC)
        self.oldest = datetime.fromtimestamp(thread.get_oldest_date())
        self.newest = datetime.fromtimestamp(thread.get_newest_date())
        self.tags = set([str(tag).decode(DB_ENC) for tag in thread.get_tags()])
        self._messages = None  # will be read on demand
        self._messages_newds = {}

    def get_thread_id(self):
        return self.tid

    def get_tags(self):
        return list(self.tags)

    def add_tags(self, tags):
        newtags = set(tags).difference(self.tags)
        if newtags:
            self.dbman.tag('thread:' + self.tid, newtags)
            self.tags = self.tags.union(newtags)

    def remove_tags(self, tags):
        rmtags = set(tags).intersection(self.tags)
        if rmtags:
            self.dbman.untag('thread:' + self.tid, tags)
            self.tags = self.tags.difference(rmtags)

    def set_tags(self, tags):
        self.dbman.tag('thread:' + self.tid, tags, remove_rest=True)
        self.tags = set(tags)

    def get_authors(self):
        return self.authors

    def get_subject(self):
        return self.subject

    def _build_messages(self, acc, msg):
        M = Message(self.dbman, msg, thread=self)
        acc[M] = {}
        self._messages_newds[M] = []

        r = msg.get_replies()
        if r is not None:
            for m in r:
                self._build_messages(acc[M], m)
                self._messages_newds[M].append(Message(self.dbman, msg, thread=self))

    def get_messages(self):
        #TODO: hack
        if not self._messages_newds:
            query = self.dbman.query('thread:' + self.tid)
            thread = query.search_threads().next()

            self._messages = {}
            for m in thread.get_toplevel_messages():
                self._build_messages(self._messages, m)
        return self._messages_newds

    def get_message_tree(self):
        if not self._messages:
            query = self.dbman.query('thread:' + self.tid)
            thread = query.search_threads().next()

            self._messages = {}
            for m in thread.get_toplevel_messages():
                self._build_messages(self._messages, m)
        return self._messages

    def get_newest_date(self):
        return self.newest

    def get_oldest_date(self):
        return self.oldest

    def get_total_messages(self):
        return self.total_messages

    def get_replies_to(self, msg):
        msgs = self.get_messages_tree()
        if msg in msgs:
            return msgs[msg].keys()
        else:
            return None


class Message:
    def __init__(self, dbman, msg, thread=None):
        self._dbman = dbman
        self._message_id = msg.get_message_id()
        self._thread_id = msg.get_thread_id()
        self._thread = thread
        self._datetime = datetime.fromtimestamp(msg.get_date())
        self._filename = str(msg.get_filename()).decode(DB_ENC)
        self._from = str(msg.get_header('From')).decode(DB_ENC)
        self._email = None  # will be read upon first use
        self._attachments = None  # will be read upon first use
        self._tags = set([str(tag).decode(DB_ENC) for tag in msg.get_tags()])

    def __str__(self):
        """prettyprint the message"""
        aname, aaddress = self.get_author()
        if not aname:
            aname = aaddress
        #tags = ','.join(self.get_tags())
        return "%s (%s)" % (aname, self.get_datestring())

    def __hash__(self):
        """Implement hash(), so we can use Message() sets"""
        return hash(self._message_id)

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
        return self._message_id

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
        """returns tags attached to this message as list of stings"""
        return list(self._tags)

    def get_thread(self):
        """returns the thread this msg belongs to as alot.db.Thread object"""
        if not self._thread:
            self._thread = seld._dbman.get_thread(self._thread_id)
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
        """adds tags from message

        :param tags: tags to add
        :type tags: list of str
        """
        self._dbman.tag('id:' + self._message_id, tags)
        self._tags = self._tags.union(tags)

    def remove_tags(self, tags):
        """remove tags from message

        :param tags: tags to remove
        :type tags: list of str
        """
        self._dbman.untag('id:' + self._message_id, tags)
        self._tags = self._tags.difference(tags)

    def get_attachments(self):
        if not self._attachments:
            self._attachments = []
            for part in self.get_message_parts():
                if part.get_content_maintype() != 'text':
                    self._attachments.append(Attachment(part))
        return self._attachments


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
        return self.part.get_content_type()

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
        if os.path.isdir(path):
            path = os.path.join(path, self.get_filename())
        FILE = open(path, "w")
        FILE.write(self.part.get_payload(decode=True))
        FILE.close()
