"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
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

    def find_message(self, mid, writeable=False):
        db = Database(path=self.path)
        if writeable:
            query = self.query('id:' + mid, writeable=writeable)
            #TODO raise exceptions here in 0<case msgcount>1
            msg = query.search_messages().next()
        else:
            msg = db.find_message(mid)
        return msg

    def get_message(self, mid):
        """returns the message with the given id and wrapps it in a Message

        :param mid: the message id of the message to look up
        :type mid: str.
        :returns:  Message -- the message.

        """
        return Message(self, self.find_message(mid))

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
        return db.create_query(querystring)


class Thread:
    def __init__(self, dbman, thread):
        self.dbman = dbman
        self.tid = thread.get_thread_id()
        self.strrep = str(thread).decode(DB_ENC)
        self.total_messages = thread.get_total_messages()
        self.topmessages = [m.get_message_id() for m in thread.get_toplevel_messages()]
        self.authors = thread.get_authors().decode(DB_ENC)
        self.subject = thread.get_subject().decode(DB_ENC)
        self.oldest = datetime.fromtimestamp(thread.get_oldest_date())
        self.newest = datetime.fromtimestamp(thread.get_newest_date())
        self.tags = set([str(tag).decode(DB_ENC) for tag in thread.get_tags()])

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
        M = Message(self.dbman, msg)
        acc[M] = {}
        r = msg.get_replies()
        if r is not None:
            for m in r:
                self._build_messages(acc[M], m)

    def get_messages(self):
        query = self.dbman.query('thread:' + self.tid)
        thread = query.search_threads().next()

        messages = {}
        for m in thread.get_toplevel_messages():
            self._build_messages(messages, m)
        return messages

    def get_newest_date(self):
        return self.newest

    def get_oldest_date(self):
        return self.oldest

    def get_total_messages(self):
        return self.total_messages


class Message:
    def __init__(self, dbman, msg):
        self.dbman = dbman
        self.mid = msg.get_message_id()
        self.datetime = datetime.fromtimestamp(msg.get_date())
        self.sender = msg.get_header('From').decode(DB_ENC)
        self.strrep = str(msg).decode(DB_ENC)
        self.email = None  # will be read upon first use
        self.tags = set([str(tag).decode(DB_ENC) for tag in msg.get_tags()])

    def __str__(self):
        return self.strrep

    def get_replies(self):
        #this doesn't work. see Note in doc -> more work here.
        return [self.dbman.find_message(mid) for mid in self.replies]

    def get_author(self):
        return helper.parse_addr(self.sender)

    def get_tags(self):
        return list(self.tags)

    def get_email(self):
        if not self.email:
            self.email = self.read_mail(self.get_filename())
        return self.email

    def read_mail(self, filename):
        try:
            f_mail = open(filename)
        except EnvironmentError:
            eml = email.message_from_string('Unable to open the file')
        else:
            eml = email.message_from_file(f_mail)
            f_mail.close()
        return eml

    def add_tags(self, tags):
        self.dbman.tag('id:' + self.mid, tags)
        self.tags = self.tags.union(tags)

    def remove_tags(self, tags):
        self.dbman.untag('id:' + self.mid, tags)
        self.tags = self.tags.difference(tags)

    def get_filename(self):
            m = self.dbman.find_message(self.mid)
            return m.get_filename()
