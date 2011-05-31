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
from notmuch import Database
from datetime import datetime
import logging
import email


class DBManager:
    """
    keeps track of your index parameters, can create notmuch.Query
    objects from its Database on demand and implements a bunch of
    database specific functions.
    """
    def __init__(self, path=None, ro=False):
        self.ro = ro
        self.path = path

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

    def get_thread(self, tid, writeable=False):
        query = self.query('thread:' + tid, writeable=writeable)
        #TODO raise exceptions here in 0<case msgcount>1
        return Thread(self, query.search_threads().next())

    def get_all_tags(self):
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return [tag for tag in db.get_all_tags()]

    def query(self, querystring, writeable=False):
        """creates notmuch.Query objects on demand

        :param querystring: The query string to use for the lookup
        :type query: str.
        :param writeable: Try to return a writeable Query object
        :type state: bool.
        :returns:  notmuch.Query -- the query object.

        """
        if writeable:
            mode = Database.MODE.READ_WRITE
        else:
            mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return db.create_query(querystring)


class Thread:
    def __init__(self, dbman, thread):
        self.dbman = dbman
        self.tid = thread.get_thread_id()
        self.strrep = str(thread)
        self.total_messages = thread.get_total_messages()
        self.topmessages = [m.get_message_id() for m in thread.get_toplevel_messages()]
        self.authors = thread.get_authors()
        self.subject = thread.get_subject()
        self.oldest = datetime.fromtimestamp(thread.get_oldest_date())
        self.newest = datetime.fromtimestamp(thread.get_newest_date())
        self.tags = set([str(tag) for tag in thread.get_tags()])

    def get_thread_id(self):
        return self.tid

    def get_tags(self):
        return list(self.tags)

    def add_tags(self, tags):
        tags = filter(lambda x: x not in self.tags, tags)
        if tags:
            query = self.dbman.query('thread:' + self.tid, writeable=True)
            for msg in query.search_messages():
                msg.freeze()
                for tag in tags:
                    msg.add_tag(tag)
                msg.thaw()
            for tag in tags:
                self.tags.add(tag)

    def remove_tags(self, tags):
        tags = filter(lambda x: x in self.tags, tags)
        if tags:
            query = self.dbman.query('thread:' + self.tid, writeable=True)
            for msg in query.search_messages():
                msg.freeze()
                for tag in tags:
                    msg.remove_tag(tag)
                msg.thaw()
            for tag in tags:
                self.tags.remove(tag)

    def set_tags(self, tags):
        query = self.dbman.query('thread:' + self.tid, writeable=True)
        self.tags = set()
        for msg in query.search_messages():
            msg.freeze()
            msg.remove_all_tags()
            for tag in tags:
                msg.add_tag(tag)
                self.tags.add(tag)
            msg.thaw()

    def get_authors(self):
        return self.authors

    def get_subject(self):
        return self.subject

    def get_toplevel_messages(self):
        return [self.dbman.get_message(mid) for mid in self.topmessages]

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
        self.strrep = str(msg)

        self.email = None  # will be read upon first use
        r = msg.get_replies()  # not iterable if None
        if r:
            self.replies = [m.get_message_id() for m in msg.get_replies()]
        else:
            self.replies = []

        self.filename = msg.get_filename()
        self.tags = set([str(tag) for tag in msg.get_tags()])

    def __str__(self):
        return self.strrep

    def get_replies(self):
        #this doesn't work. see Note in doc -> more work here.
        return [self.dbman.find_message(mid) for mid in self.replies]

    def get_tags(self):
        return list(self.tags)

    def get_email(self):
        if not self.email:
            self.email = self.read_mail(self.filename)
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
        msg = self.dbman.find_message(self.mid)
        msg.freeze()
        for tag in tags:
            msg.add_tag(tag)
            self.tags.add(tag)
            logging.debug('tag %s' % tags)
        msg.thaw()

    def remove_tags(self, tags):
        msg = self.dbman.find_message(self.mid, writeable=True)
        msg.freeze()
        for tag in tags:
            msg.remove_tag(tag)
            try:
                self.tags.remove(tag)
            except KeyError:
                pass  # tag not in self.tags
            logging.debug('untag %s' % tags)
        msg.thaw()
