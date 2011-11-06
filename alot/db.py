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
from notmuch import Database, NotmuchError, XapianError
import notmuch
import multiprocessing

from datetime import datetime
from collections import deque

from message import Message
from settings import notmuchconfig as config

DB_ENC = 'utf-8'


class DatabaseError(Exception):
    pass


class DatabaseROError(DatabaseError):
    pass


class DatabaseLockedError(DatabaseError):
    pass


class NotmuchProcess(multiprocessing.Process):
  def __init__(self, path, query, pipe):
    multiprocessing.Process.__init__(self)
    self.path = path
    self.query = query
    self.pipe = pipe
    self.daemon = True

  def run(self):
    mode = Database.MODE.READ_ONLY
    db = Database(path=self.path, mode=mode)
    q = db.create_query(self.query)
    try:
      for a in q.search_threads():
        self.pipe.send(a.get_thread_id())
      self.pipe.send(None)
    except IOError:
      # looks like the main process exited, so we stop
      pass


class DBManager(object):
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
                current_item = self.writequeue.popleft()
                cmd, querystring, tags, sync = current_item
                try:  # make this a transaction
                    db.begin_atomic()
                except XapianError:
                    raise DatabaseError()
                query = db.create_query(querystring)
                for msg in query.search_messages():
                    msg.freeze()
                    if cmd == 'tag':
                        for tag in tags:
                            msg.add_tag(tag.encode(DB_ENC),
                                        sync_maildir_flags=sync)
                    if cmd == 'set':
                        msg.remove_all_tags()
                        for tag in tags:
                            msg.add_tag(tag.encode(DB_ENC),
                                        sync_maildir_flags=sync)
                    elif cmd == 'untag':
                        for tag in tags:
                            msg.remove_tag(tag.encode(DB_ENC),
                                          sync_maildir_flags=sync)
                    msg.thaw()

                # end transaction and reinsert queue item on error
                if db.end_atomic() != notmuch.STATUS.SUCCESS:
                    self.writequeue.appendleft(current_item)

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
        sync_maildir_flags = config.getboolean('maildir', 'synchronize_flags')
        if remove_rest:
            self.writequeue.append(('set', querystring, tags,
                                    sync_maildir_flags))
        else:
            self.writequeue.append(('tag', querystring, tags,
                                    sync_maildir_flags))

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
        sync_maildir_flags = config.getboolean('maildir', 'synchronize_flags')
        self.writequeue.append(('untag', querystring, tags,
                                sync_maildir_flags))

    def count_messages(self, querystring):
        """returns number of messages that match querystring"""
        return self.query_simple(querystring).count_messages()

    def search_thread_ids(self, querystring):
        """returns the ids of all threads that match the querystring
        This copies! all integer thread ids into an new list."""
        
        return self.query_threaded(querystring)

    def get_thread(self, tid):
        """returns the thread with given id as alot.db.Thread object"""
        query = self.query_simple('thread:' + tid)
        #TODO raise exceptions here in 0<case msgcount>1
        try:
            return Thread(self, query.search_threads().next())
        except:
            return None

    def get_message(self, mid):
        """returns the message with given id as alot.message.Message object"""
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        msg = db.find_message(mid)
        return Message(self, msg)

    def get_all_tags(self):
        """returns all tags as list of strings"""
        db = Database(path=self.path)
        return [t for t in db.get_all_tags()]

    def query_threaded(self, querystring):
        """creates notmuch.Query objects on demand with multiprocess

        :param querystring: The query string to use for the lookup
        :type query: str.
        :returns:  pipe with thread ids

        """
        (i, o) = multiprocessing.Pipe(False)
        t = NotmuchProcess(self.path, querystring, o)
        t.start()
        return i
 
    def query_simple(self, querystring):
        """creates notmuch.Query objects on demand

        :param querystring: The query string to use for the lookup
        :type query: str.
        :returns:  notmuch.Query -- the query object.

        """
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return db.create_query(querystring)


class Thread(object):
    def __init__(self, dbman, thread):
        """
        :param dbman: db manager that is used for further lookups
        :type dbman: alot.db.DBManager
        :param msg: the wrapped thread
        :type msg: notmuch.database.Thread
        """
        self._dbman = dbman
        self._id = thread.get_thread_id()
        self.refresh(thread)

    def refresh(self, thread=None):
        if not thread:
            query = self._dbman.query_simple('thread:' + self._id)
            thread = query.search_threads().next()
        self._total_messages = thread.get_total_messages()
        self._authors = thread.get_authors()
        self._subject = thread.get_subject()
        ts = thread.get_oldest_date()

        try:
            self._oldest_date = datetime.fromtimestamp(ts)
        except ValueError:  # year is out of range
            self._oldest_date = None
        try:
            timestamp = thread.get_newest_date()
            self._newest_date = datetime.fromtimestamp(timestamp)
        except ValueError:  # year is out of range
            self._newest_date = None

        self._tags = set([t for t in thread.get_tags()])
        self._messages = {}  # this maps messages to its children
        self._toplevel_messages = []

    def __str__(self):
        return "thread:%s: %s" % (self._id, self.get_subject())

    def get_thread_id(self):
        """returns id of this thread"""
        return self._id

    def get_tags(self):
        """returns tags attached to this thread as list of strings"""
        l = list(self._tags)
        l.sort()
        return l

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
        if tags != self._tags:
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
            query = self._dbman.query_simple('thread:' + self._id)
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
