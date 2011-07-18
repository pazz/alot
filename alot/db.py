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


class DatabaseError(Exception):
    pass


class DatabaseROError(DatabaseError):
    pass


class DatabaseLockedError(DatabaseError):
    pass


class DBManager:
    """
    keeps track of your index parameters, can create notmuch.Query
    objects from its Database on demand and implements a bunch of
    database specific functions.
    """
    def __init__(self, path=None, ro=False):
        """
        :param path: absolute path to the notmuch index
        :type path: str
        :param ro: open the index in read-only mode
        :type ro: boolean
        """
        self.ro = ro
        self.path = path
        self.writequeue = deque([])

    def flush(self):
        """
        tries to flush all queued write commands to the index.

        :exception: :exc:`DatabaseROError` if db is opened in read-only mode
        :exception: :exc:`DatabaseLockedError` if db is locked
        """
        if self.ro:
            raise DatabaseROError()
        if self.writequeue:
            try:
                mode = Database.MODE.READ_WRITE
                db = Database(path=self.path, mode=mode)
            except NotmuchError:
                raise DatabaseLockedError()
            while self.writequeue:
                cmd, querystring, tags = self.writequeue.popleft()
                query = db.create_query(querystring)
                for msg in query.search_messages():
                    msg.freeze()
                    if cmd == 'tag':
                        for tag in tags:
                            msg.add_tag(tag.encode(DB_ENC),
                                        sync_maildir_flags=True)
                    if cmd == 'set':
                        msg.remove_all_tags()
                        for tag in tags:
                            msg.add_tag(tag.encode(DB_ENC),
                                        sync_maildir_flags=True)
                    elif cmd == 'untag':
                        for tag in tags:
                            msg.remove_tag(tag.encode(DB_ENC),
                                          sync_maildir_flags=True)
                    msg.thaw()

    def tag(self, querystring, tags, remove_rest=False):
        """
        add tags to all matching messages. Raises
        :exc:`DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :type querystring: str
        :param tags: a list of tags to be added
        :type tags: list of str
        :param remove_rest: remove tags from matching messages before tagging
        :type remove_rest: boolean
        :exception: :exc:`NotmuchError`
        """
        if self.ro:
            raise DatabaseROError()
        if remove_rest:
            self.writequeue.append(('set', querystring, tags))
        else:
            self.writequeue.append(('tag', querystring, tags))
        self.flush()

    def untag(self, querystring, tags):
        """
        add tags to all matching messages. Raises
        :exc:`DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :type querystring: str
        :param tags: a list of tags to be added
        :type tags: list of str
        :exception: :exc:`NotmuchError`
        """
        if self.ro:
            raise DatabaseROError()
        self.writequeue.append(('untag', querystring, tags))
        self.flush()

    def count_messages(self, querystring):
        """returns number of messages that match querystring"""
        return self.query(querystring).count_messages()

    def search_thread_ids(self, querystring):
        """returns the ids of all threads that match the querystring
        This copies! all integer thread ids into an new list."""
        threads = self.query(querystring).search_threads()
        return [thread.get_thread_id() for thread in threads]

    def get_thread(self, tid):
        """returns the thread with given id as alot.db.Thread object"""
        query = self.query('thread:' + tid)
        #TODO raise exceptions here in 0<case msgcount>1
        return Thread(self, query.search_threads().next())

    def get_all_tags(self):
        """returns all tags as list of strings"""
        db = Database(path=self.path)
        return list(db.get_all_tags())

    def query(self, querystring):
        """creates notmuch.Query objects on demand

        :param querystring: The query string to use for the lookup
        :type query: str.
        :returns:  notmuch.Query -- the query object.

        """
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return db.create_query(querystring)


class Thread:
    def __init__(self, dbman, thread):
        """
        :param dbman: db manager that is used for further lookups
        :type dbman: alot.db.DBManager
        :param msg: the wrapped thread
        :type msg: notmuch.database.Thread
        """
        self._dbman = dbman
        self._id = thread.get_thread_id()
        self._total_messages = thread.get_total_messages()
        self._authors = str(thread.get_authors()).decode(DB_ENC)
        self._subject = str(thread.get_subject()).decode(DB_ENC)
        self._oldest_date = datetime.fromtimestamp(thread.get_oldest_date())
        self._newest_date = datetime.fromtimestamp(thread.get_newest_date())
        self._tags = set(thread.get_tags())
        self._messages = {}  # this maps messages to its children
        self._toplevel_messages = []

    def __str__(self):
        return "thread:%s: %s" % (self._id, self.get_subject())

    def get_thread_id(self):
        """returns id of this thread"""
        return self._id

    def get_tags(self):
        """returns tags attached to this thread as list of strings"""
        return list(self._tags)

    def add_tags(self, tags):
        """adds tags to all messages in this thread

        :param tags: tags to add
        :type tags: list of str
        """
        newtags = set(tags).difference(self._tags)
        if newtags:
            self._dbman.tag('thread:' + self._id, newtags)
            self._tags = self._tags.union(newtags)

    def remove_tags(self, tags):
        """remove tags from all messages in this thread

        :param tags: tags to remove
        :type tags: list of str
        """
        rmtags = set(tags).intersection(self._tags)
        if rmtags:
            self._dbman.untag('thread:' + self._id, tags)
            self._tags = self._tags.difference(rmtags)

    def set_tags(self, tags):
        """set tags of all messages in this thread. This removes all tags and
        attaches the given ones in one step.

        :param tags: tags to add
        :type tags: list of str
        """
        self._dbman.tag('thread:' + self._id, tags, remove_rest=True)
        self._tags = set(tags)

    def get_authors(self):  # TODO: make this return a list of strings
        """returns all authors in this thread"""
        return self._authors

    def get_subject(self):
        """returns this threads subject"""
        return self._subject

    def get_toplevel_messages(self):
        """returns all toplevel messages as list of :class:`Message`"""
        if not self._messages:
            self.get_messages()
        return self._toplevel_messages

    def get_messages(self):
        """returns all messages in this thread

        :returns: dict mapping all contained :class:`Message`s to a list of
        their respective children.
        """
        if not self._messages:
            query = self._dbman.query('thread:' + self._id)
            thread = query.search_threads().next()

            def accumulate(acc, msg):
                M = Message(self._dbman, msg, thread=self)
                acc[M] = []
                r = msg.get_replies()
                if r is not None:
                    for m in r:
                        acc[M].append(accumulate(acc, m))
                return M

            self._messages = {}
            for m in thread.get_toplevel_messages():
                self._toplevel_messages.append(accumulate(self._messages, m))
        return self._messages

    def get_replies_to(self, msg):
        """returns all replies to the given message

        :param msg: the parent message, must be contained in thread
        :type msg: alot.sb.Message
        """
        mid = msg.get_message_id()
        msg_hash = self.get_messages()
        for m in msg_hash.keys():
            if m.get_message_id() == mid:
                return msg_hash[m]
        return None

    def get_newest_date(self):
        """returns date header of newest message in this thread as datetime"""
        return self._newest_date

    def get_oldest_date(self):
        """returns date header of oldest message in this thread as datetime"""
        return self._oldest_date

    def get_total_messages(self):
        """returns number of contained messages"""
        return self._total_messages


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
        self._from = msg.get_header('From').decode(DB_ENC)
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
        return list(self._tags)

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
