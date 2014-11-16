# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import operator
from datetime import datetime

from message import Message
from alot.settings import settings


class Thread(object):
    """
    A wrapper around a notmuch mailthread (:class:`notmuch.database.Thread`)
    that ensures persistence of the thread: It can be safely read multiple
    times, its manipulation is done via a :class:`alot.db.DBManager` and it can
    directly provide contained messages as :class:`~alot.db.message.Message`.
    """

    def __init__(self, dbman, thread):
        """
        :param dbman: db manager that is used for further lookups
        :type dbman: :class:`~alot.db.DBManager`
        :param thread: the wrapped thread
        :type thread: :class:`notmuch.database.Thread`
        """
        self._dbman = dbman
        self._id = thread.get_thread_id()
        self.refresh(thread)

    def refresh(self, thread=None):
        """refresh thread metadata from the index"""
        if not thread:
            thread = self._dbman._get_notmuch_thread(self._id)

        self._total_messages = thread.get_total_messages()
        self._notmuch_authors_string = thread.get_authors()

        subject_type = settings.get('thread_subject')
        if subject_type == 'notmuch':
            subject = thread.get_subject()
        elif subject_type == 'oldest':
            try:
                first_msg = list(thread.get_toplevel_messages())[0]
                subject = first_msg.get_header('subject')
            except IndexError:
                subject = ''
        self._subject = subject

        self._authors = None
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

    def get_tags(self, intersection=False):
        """
        returns tagsstrings attached to this thread

        :param intersection: return tags present in all contained messages
                             instead of in at least one (union)
        :type intersection: bool
        :rtype: set of str
        """
        tags = set(list(self._tags))
        if intersection:
            for m in self.get_messages().keys():
                tags = tags.intersection(set(m.get_tags()))
        return tags

    def add_tags(self, tags, afterwards=None, remove_rest=False):
        """
        add `tags` to all messages in this thread

        .. note::

            This only adds the requested operation to this objects
            :class:`DBManager's <alot.db.DBManager>` write queue.
            You need to call :meth:`DBManager.flush <alot.db.DBManager.flush>`
            to actually write out.

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

        self._dbman.tag('thread:' + self._id, tags, afterwards=myafterwards,
                        remove_rest=remove_rest)

    def remove_tags(self, tags, afterwards=None):
        """
        remove `tags` (list of str) from all messages in this thread

        .. note::

            This only adds the requested operation to this objects
            :class:`DBManager's <alot.db.DBManager>` write queue.
            You need to call :meth:`DBManager.flush <alot.db.DBManager.flush>`
            to actually write out.

        :param tags: a list of tags to be added
        :type tags: list of str
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :type afterwards: callable
        """
        rmtags = set(tags).intersection(self._tags)
        if rmtags:

            def myafterwards():
                self._tags = self._tags.difference(tags)
                if callable(afterwards):
                    afterwards()
            self._dbman.untag('thread:' + self._id, tags, myafterwards)
            self._tags = self._tags.difference(rmtags)

    def get_authors(self):
        """
        returns a list of authors (name, addr) of the messages.
        The authors are ordered by msg date and unique (by name/addr).

        :rtype: list of (str, str)
        """
        if self._authors is None:
            seen = {}
            msgs = self.get_messages().keys()
            msgs_with_date = filter(lambda m: m.get_date() is not None, msgs)
            msgs_without_date = filter(lambda m: m.get_date() is None, msgs)
            # sort messages with date and append the others
            msgs_with_date.sort(None, lambda m: m.get_date())
            msgs = msgs_with_date + msgs_without_date
            orderby = settings.get('thread_authors_order_by')
            if orderby == 'latest_message':
                for i, m in enumerate(msgs):
                    pair = m.get_author()
                    seen[pair] = i
            else: # i.e. first_message
                for i, m in enumerate(msgs):
                    pair = m.get_author()
                    if pair not in seen:
                        seen[pair] = i
            self._authors = [ name for name, addr in
                sorted(seen.items(), key=operator.itemgetter(1)) ]
        return self._authors

    def get_authors_string(self, own_addrs=None, replace_own=None):
        """
        returns a string of comma-separated authors
        Depending on settings, it will substitute "me" for author name if
        address is user's own.

        :param own_addrs: list of own email addresses to replace
        :type own_addrs: list of str
        :param replace_own: whether or not to actually do replacement
        :type replace_own: bool
        :rtype: str
        """
        if replace_own is None:
            replace_own = settings.get('thread_authors_replace_me')
        if replace_own:
            if own_addrs is None:
                own_addrs = settings.get_addresses()
            authorslist = []
            for aname, aaddress in self.get_authors():
                if aaddress in own_addrs:
                    aname = settings.get('thread_authors_me')
                if not aname:
                    aname = aaddress
                if aname not in authorslist:
                    authorslist.append(aname)
            return ', '.join(authorslist)
        else:
            return self._notmuch_authors_string

    def get_subject(self):
        """returns subject string"""
        return self._subject

    def get_toplevel_messages(self):
        """
        returns all toplevel messages contained in this thread.
        This are all the messages without a parent message
        (identified by 'in-reply-to' or 'references' header.

        :rtype: list of :class:`~alot.db.message.Message`
        """
        if not self._messages:
            self.get_messages()
        return self._toplevel_messages

    def get_messages(self):
        """
        returns all messages in this thread as dict mapping all contained
        messages to their direct responses.

        :rtype: dict mapping :class:`~alot.db.message.Message` to a list of
                :class:`~alot.db.message.Message`.
        """
        if not self._messages:  # if not already cached
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
        """
        returns all replies to the given message contained in this thread.

        :param msg: parent message to look up
        :type msg: :class:`~alot.db.message.Message`
        :returns: list of :class:`~alot.db.message.Message` or `None`
        """
        mid = msg.get_message_id()
        msg_hash = self.get_messages()
        for m in msg_hash.keys():
            if m.get_message_id() == mid:
                return msg_hash[m]
        return None

    def get_newest_date(self):
        """
        returns date header of newest message in this thread as
        :class:`~datetime.datetime`
        """
        return self._newest_date

    def get_oldest_date(self):
        """
        returns date header of oldest message in this thread as
        :class:`~datetime.datetime`
        """
        return self._oldest_date

    def get_total_messages(self):
        """returns number of contained messages"""
        return self._total_messages

    def matches(self, query):
        """
        Check if this thread matches the given notmuch query.

        :param query: The query to check against
        :type query: string
        :returns: True if this thread matches the given query, False otherwise
        :rtype: bool
        """
        thread_query = 'thread:{tid} AND {subquery}'.format(tid=self._id,
                                                            subquery=query)
        num_matches = self._dbman.count_messages(thread_query)
        return num_matches > 0
