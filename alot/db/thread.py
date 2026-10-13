# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from ..helper import string_sanitize
from .message import Message
from ..settings.const import settings
from .utils import decode_header

if TYPE_CHECKING:
    import notmuch2
    from .manager import DBManager


class Thread:
    """
    A wrapper around a notmuch mailthread (:class:`notmuch2.Thread`)
    that ensures persistence of the thread: It can be safely read multiple
    times, its manipulation is done via a :class:`alot.db.DBManager` and it can
    directly provide contained messages as :class:`~alot.db.message.Message`.
    """

    def __init__(self, dbman: 'DBManager', thread: 'notmuch2.Thread') -> None:
        """
        :param dbman: db manager that is used for further lookups
        :param thread: the wrapped thread
        """
        self._dbman = dbman
        self._authors: list[tuple[str, str]] | None = None
        self._id: str = thread.threadid
        self._messages: dict[Message, list[Message]] = {}
        self._tags: set[str] = set()

        self.refresh(thread)

    def refresh(self, thread: 'notmuch2.Thread | None' = None) -> None:
        """refresh thread metadata from the index"""
        if not thread:
            with self._dbman._with_notmuch_thread(self._id) as thread:
                self._refresh(thread)
        else:
            self._refresh(thread)

    def _refresh(self, thread: 'notmuch2.Thread') -> None:
        self._total_messages = len(thread)
        self._notmuch_authors_string: str = thread.authors

        subject_type = settings.get('thread_subject')
        if subject_type == 'notmuch':
            subject = string_sanitize(thread.subject)
        elif subject_type == 'oldest':
            try:
                first_msg = list(thread.toplevel())[0]
                subject = decode_header(first_msg.header('subject'))
            except (IndexError, LookupError):
                subject = ''
        self._subject = subject

        self._authors = None
        ts = thread.first

        self._oldest_date: datetime | None
        self._newest_date: datetime | None
        try:
            self._oldest_date = datetime.fromtimestamp(ts)
        except ValueError:  # year is out of range
            self._oldest_date = None
        try:
            timestamp = thread.last
            self._newest_date = datetime.fromtimestamp(timestamp)
        except ValueError:  # year is out of range
            self._newest_date = None

        self._tags = {t for t in thread.tags}
        self._messages = {}  # this maps messages to its children
        self._toplevel_messages: list[Message] = []

    def __str__(self) -> str:
        return "thread:%s: %s" % (self._id, self.get_subject())

    def get_thread_id(self) -> str:
        """returns id of this thread"""
        return self._id

    def get_tags(self, intersection: bool = False) -> set[str]:
        """
        returns tagsstrings attached to this thread

        :param intersection: return tags present in all contained messages
                             instead of in at least one (union)
        """
        tags = set(list(self._tags))
        if intersection:
            for m in self.get_messages().keys():
                tags = tags.intersection(set(m.get_tags()))
        return tags

    def add_tags(self, tags: list[str],
                 afterwards: Callable[[], None] | None = None,
                 remove_rest: bool = False) -> None:
        """
        add `tags` to all messages in this thread

        .. note::

            This only adds the requested operation to this objects
            :class:`DBManager's <alot.db.DBManager>` write queue.
            You need to call :meth:`DBManager.flush <alot.db.DBManager.flush>`
            to actually write out.

        :param tags: a list of tags to be added
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :param remove_rest: remove all other tags
        """
        def myafterwards() -> None:
            if remove_rest:
                self._tags = set(tags)
            else:
                self._tags = self._tags.union(tags)
            if callable(afterwards):
                afterwards()

        self._dbman.tag('thread:' + self._id, tags, afterwards=myafterwards,
                        remove_rest=remove_rest)

    def remove_tags(self, tags: list[str],
                    afterwards: Callable[[], None] | None = None) -> None:
        """
        remove `tags` (list of str) from all messages in this thread

        .. note::

            This only adds the requested operation to this objects
            :class:`DBManager's <alot.db.DBManager>` write queue.
            You need to call :meth:`DBManager.flush <alot.db.DBManager.flush>`
            to actually write out.

        :param tags: a list of tags to be added
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        """
        rmtags = set(tags).intersection(self._tags)
        if rmtags:

            def myafterwards() -> None:
                self._tags = self._tags.difference(tags)
                if callable(afterwards):
                    afterwards()
            self._dbman.untag('thread:' + self._id, tags, myafterwards)
            self._tags = self._tags.difference(rmtags)

    def get_authors(self) -> list[tuple[str, str]]:
        """
        returns a list of authors (name, addr) of the messages.
        The authors are ordered by msg date and unique (by name/addr).
        """
        if self._authors is None:
            # Sort messages with date first (by date ascending), and those
            # without a date last.
            msgs = sorted(self.get_messages().keys(),
                          key=lambda m: m.get_date() or datetime.max)

            orderby = settings.get('thread_authors_order_by')
            self._authors = []
            if orderby == 'latest_message':
                for m in msgs:
                    pair = m.get_author()
                    if pair in self._authors:
                        self._authors.remove(pair)
                    self._authors.append(pair)
            else:  # i.e. first_message
                for m in msgs:
                    pair = m.get_author()
                    if pair not in self._authors:
                        self._authors.append(pair)

        return self._authors

    def get_authors_string(self) -> str:
        """
        returns a string of comma-separated authors
        Depending on settings, it will substitute "me" for author name if
        address is user's own.
        """
        if settings.get('thread_authors_replace_me'):
            own_accts = settings.get_accounts()
            authorslist = []
            for aname, aaddress in self.get_authors():
                for account in own_accts:
                    if account.matches_address(aaddress):
                        aname = settings.get('thread_authors_me')
                        break
                if not aname:
                    aname = aaddress
                if aname not in authorslist:
                    authorslist.append(aname)
            return ', '.join(authorslist)
        else:
            return self._notmuch_authors_string

    def get_subject(self) -> str:
        """returns subject string"""
        return self._subject

    def get_toplevel_messages(self) -> list[Message]:
        """
        returns all toplevel messages contained in this thread.
        This are all the messages without a parent message
        (identified by 'in-reply-to' or 'references' header.
        """
        if not self._messages:
            self.get_messages()
        return self._toplevel_messages

    def get_messages(self) -> dict[Message, list[Message]]:
        """
        returns all messages in this thread as dict mapping all contained
        messages to their direct responses.
        """
        if not self._messages:  # if not already cached
            with self._dbman._with_notmuch_thread(self._id) as thread:

                def accumulate(acc: dict[Message, list[Message]],
                               msg: 'notmuch2.Message') -> Message:
                    M = Message(self._dbman, msg, thread=self)
                    acc[M] = []
                    for m in msg.replies():
                        acc[M].append(accumulate(acc, m))
                    return M

                self._messages = {}
                for m in thread.toplevel():
                    self._toplevel_messages.append(accumulate(self._messages,
                                                              m))
        return self._messages

    def get_replies_to(self, msg: Message) -> list[Message] | None:
        """
        returns all replies to the given message contained in this thread.

        :param msg: parent message to look up
        """
        mid = msg.get_message_id()
        msg_hash = self.get_messages()
        for m in msg_hash.keys():
            if m.get_message_id() == mid:
                return msg_hash[m]
        return None

    def get_newest_date(self) -> datetime | None:
        """returns date header of newest message in this thread"""
        return self._newest_date

    def get_oldest_date(self) -> datetime | None:
        """returns date header of oldest message in this thread"""
        return self._oldest_date

    def get_total_messages(self) -> int:
        """returns number of contained messages"""
        return self._total_messages

    def matches(self, query: str) -> bool:
        """
        Check if this thread matches the given notmuch query.

        :param query: The query to check against
        :returns: True if this thread matches the given query, False otherwise
        """
        thread_query = 'thread:{tid} AND {subquery}'.format(tid=self._id,
                                                            subquery=query)
        num_matches = self._dbman.count_messages(thread_query)
        return num_matches > 0
