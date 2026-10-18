# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from collections import deque
from collections.abc import Callable, Iterator
import contextlib
import itertools
import logging
from typing import Any, cast

from notmuch2 import Database, NotmuchError, XapianError
import notmuch2

from .errors import DatabaseError
from .errors import DatabaseLockedError
from .errors import DatabaseROError
from .errors import NonexistantObjectError
from .message import Message
from .thread import Thread
from .utils import is_subdir_of, narrow_query
from ..settings.const import settings


class DBManager:
    """
    Keeps track of your index parameters, maintains a write-queue and
    lets you look up threads and messages directly to the persistent wrapper
    classes.
    """
    _sort_orders = {
        'oldest_first': notmuch2.Database.SORT.OLDEST_FIRST,
        'newest_first': notmuch2.Database.SORT.NEWEST_FIRST,
        'unsorted': notmuch2.Database.SORT.UNSORTED,
        'message_id': notmuch2.Database.SORT.MESSAGE_ID,
    }
    """constants representing sort orders"""

    def __init__(self, path: str | None = None, ro: bool = False,
                 config: str | None = None) -> None:
        """
        :param path: absolute path to the notmuch index
        :param ro: open the index in read-only mode
        :param config: absolute path to the notmuch config file
        """
        self.ro = ro
        self.path = path
        self.config = config
        # (command, callback, arguments...)
        self.writequeue: deque[tuple[Any, ...]] = deque([])

    @property
    def exclude_tags(self) -> list[str]:
        exclude_tags: list[str] | None = settings.get('exclude_tags')
        if exclude_tags is not None:
            return exclude_tags
        return cast(list[str],
                    settings.get_notmuch_setting('search', 'exclude_tags'))

    def flush(self) -> None:
        """
        write out all queued write-commands in order, each one in a separate
        :meth:`atomic <notmuch2.Database.atomic>` transaction.

        If this fails the current action is rolled back, stays in the write
        queue and an exception is raised.
        You are responsible to retry flushing at a later time if you want to
        ensure that the cached changes are applied to the database.

        :exception: :exc:`~errors.DatabaseROError` if db is opened read-only
        :exception: :exc:`~errors.DatabaseLockedError` if db is locked
        """
        if self.ro:
            raise DatabaseROError()
        if self.writequeue:
            # read notmuch's config regarding imap flag synchronization
            sync = settings.get_notmuch_setting('maildir', 'synchronize_flags')

            # go through writequeue entries
            while self.writequeue:
                current_item = self.writequeue.popleft()
                logging.debug('write-out item: %s', str(current_item))

                # watch out for notmuch errors to re-insert current_item
                # to the queue on errors
                try:
                    # the first two coordinates are cnmdname and post-callback
                    cmd, afterwards = current_item[:2]
                    logging.debug('cmd created')

                    # acquire a writeable db handler
                    try:
                        mode = Database.MODE.READ_WRITE
                        db = Database(path=self.path, mode=mode,
                                      config=self.config)
                    except NotmuchError:
                        raise DatabaseLockedError()
                    logging.debug('got write lock')

                    # make this a transaction
                    with db.atomic():
                        logging.debug('got atomic')

                        if cmd == 'add':
                            logging.debug('add')
                            path, tags = current_item[2:]
                            msg, _ = db.add(path, sync_flags=sync)
                            logging.debug('added msg')
                            with msg.frozen():
                                logging.debug('freeze')
                                for tag in tags:
                                    msg.tags.add(tag)
                                if sync:
                                    msg.tags.to_maildir_flags()
                                logging.debug('added tags ')
                            logging.debug('thaw')

                        elif cmd == 'remove':
                            path = current_item[2]
                            db.remove(path)

                        elif cmd == 'setconfig':
                            key = current_item[2]
                            value = current_item[3]
                            db.config[key] = value

                        else:  # tag/set/untag
                            querystring, tags = current_item[2:]
                            if cmd in ('tag', 'untag') and tags:
                                querystring = self._needing_change(
                                    querystring, tags, cmd == 'tag')
                            if cmd == 'toggle':
                                presenttags = self.collect_tags(querystring)
                                to_remove: list[str] = []
                                to_add: list[str] = []
                                for tag in tags:
                                    if tag in presenttags:
                                        to_remove.append(tag)
                                    else:
                                        to_add.append(tag)

                            for msg in db.messages(querystring):
                                with msg.frozen():
                                    if cmd == 'toggle':
                                        for tag in to_remove:
                                            msg.tags.discard(tag)
                                        for tag in to_add:
                                            msg.tags.add(tag)
                                    else:
                                        if cmd == 'set':
                                            msg.tags.clear()

                                        for tag in tags:
                                            if cmd == 'tag' or cmd == 'set':
                                                msg.tags.add(tag)
                                            elif cmd == 'untag':
                                                msg.tags.discard(tag)
                                    if sync:
                                        msg.tags.to_maildir_flags()

                        logging.debug('ended atomic')

                    # close db
                    db.close()
                    logging.debug('closed db')

                    # call post-callback
                    if callable(afterwards):
                        logging.debug(str(afterwards))
                        afterwards()
                        logging.debug('called callback')

                # re-insert item to the queue upon Xapian/NotmuchErrors
                except (XapianError, NotmuchError) as e:
                    logging.exception(e)
                    self.writequeue.appendleft(current_item)
                    raise DatabaseError(str(e))
                except DatabaseLockedError as e:
                    logging.debug('index temporarily locked')
                    self.writequeue.appendleft(current_item)
                    raise e
                logging.debug('flush finished')

    @staticmethod
    def _needing_change(querystring: str, tags: list[str], add: bool) -> str:
        """narrow `querystring` to the messages whose tags change when
        adding (or removing) `tags`: notmuch rewrites each message it
        touches, which is slow on large result sets"""
        terms = ['tag:"%s"' % t.replace('"', '""') for t in tags]
        if add:
            change = 'NOT (%s)' % ' AND '.join(terms)
        else:
            change = '(%s)' % ' OR '.join(terms)
        return narrow_query(querystring, change)

    def tag(self, querystring: str, tags: list[str],
            afterwards: Callable[[], None] | None = None,
            remove_rest: bool = False) -> None:
        """
        add tags to messages matching `querystring`.
        This appends a tag operation to the write queue and raises
        :exc:`~errors.DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :param tags: a list of tags to be added
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :param remove_rest: remove tags from matching messages before tagging
        :exception: :exc:`~errors.DatabaseROError`

        .. note::
            This only adds the requested operation to the write queue.
            You need to call :meth:`DBManager.flush` to actually write out.
        """
        if self.ro:
            raise DatabaseROError()
        if remove_rest:
            self.writequeue.append(('set', afterwards, querystring, tags))
        else:
            self.writequeue.append(('tag', afterwards, querystring, tags))

    def untag(self, querystring: str, tags: list[str],
              afterwards: Callable[[], None] | None = None) -> None:
        """
        removes tags from messages that match `querystring`.
        This appends an untag operation to the write queue and raises
        :exc:`~errors.DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :param tags: a list of tags to be added
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :exception: :exc:`~errors.DatabaseROError`

        .. note::
            This only adds the requested operation to the write queue.
            You need to call :meth:`DBManager.flush` to actually write out.
        """
        if self.ro:
            raise DatabaseROError()
        self.writequeue.append(('untag', afterwards, querystring, tags))

    def toggle_tags(self, querystring: str, tags: list[str],
                    afterwards: Callable[[], None] | None = None) -> None:
        """
        toggles tags from messages that match `querystring`.
        This appends a toggle operation to the write queue and raises
        :exc:`~errors.DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :param tags: a list of tags to be added
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :exception: :exc:`~errors.DatabaseROError`

        .. note::
            This only adds the requested operation to the write queue.
            You need to call :meth:`DBManager.flush` to actually write out.
        """
        if self.ro:
            raise DatabaseROError()
        self.writequeue.append(('toggle', afterwards, querystring, tags))

    def count_messages(self, querystring: str) -> int:
        """returns number of messages that match `querystring`"""
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY,
                      config=self.config)
        count: int = db.count_messages(querystring,
                                       exclude_tags=self.exclude_tags)
        return count

    def collect_tags(self, querystring: str) -> list[str]:
        """returns tags of messages that match `querystring`"""
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY,
                      config=self.config)
        tagset = notmuch2._tags.ImmutableTagSet(
            db.messages(querystring,
                        exclude_tags=self.exclude_tags),
            '_iter_p',
            notmuch2.capi.lib.notmuch_messages_collect_tags)
        return [t for t in tagset]

    def count_threads(self, querystring: str) -> int:
        """returns number of threads that match `querystring`"""
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY,
                      config=self.config)
        count: int = db.count_threads(querystring,
                                      exclude_tags=self.exclude_tags)
        return count

    @contextlib.contextmanager
    def _with_notmuch_thread(self, tid: str) -> Iterator[notmuch2.Thread]:
        """returns :class:`notmuch2.Thread` with given id"""
        with Database(path=self.path, mode=Database.MODE.READ_ONLY,
                      config=self.config) as db:
            try:
                thread = next(db.threads('thread:' + tid))
            except (StopIteration, NotmuchError):
                errmsg = 'no thread with id %s exists!' % tid
                raise NonexistantObjectError(errmsg)
            yield thread

    def get_thread(self, tid: str) -> Thread:
        """returns :class:`Thread` with given thread id"""
        with self._with_notmuch_thread(tid) as thread:
            return Thread(self, thread)

    @contextlib.contextmanager
    def _with_notmuch_message(self, mid: str) -> Iterator[notmuch2.Message]:
        """returns :class:`notmuch2.Message` with given id"""
        with Database(path=self.path, mode=Database.MODE.READ_ONLY,
                      config=self.config) as db:
            try:
                msg = db.find(mid)
            except (LookupError, NotmuchError):
                errmsg = 'no message with id %s exists!' % mid
                raise NonexistantObjectError(errmsg)
            yield msg

    def get_message(self, mid: str) -> Message:
        """returns :class:`Message` with given message id"""
        with self._with_notmuch_message(mid) as msg:
            return Message(self, msg)

    def get_all_tags(self) -> list[str]:
        """returns all tagsstrings used in the database"""
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY,
                      config=self.config)
        return [t for t in db.tags]

    def get_named_queries(self) -> dict[str, str]:
        """
        returns the named queries stored in the database, mapping alias to
        full query string.
        """
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY,
                      config=self.config)
        return {k[6:]: db.config[k] for k in db.config if
                k.startswith('query.')}

    def get_threads(self, querystring: str, sort: str = 'newest_first',
                    limit: int | None = None) -> tuple[Iterator[str], int]:
        """
        asynchronously look up thread ids matching `querystring`.

        :param querystring: The query string to use for the lookup
        :param sort: Sort order. one of ['oldest_first', 'newest_first',
                     'message_id', 'unsorted']
        :param limit: Limit the number of threads returned.
        :returns: a thread ID iterator and the number of matched messages
            (the iterator will have at most limit many items and the counted
            messages are also influenced by this limit)
        """
        assert sort in self._sort_orders
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY,
                      config=self.config)
        thread_iterator = db.threads(querystring,
                                     sort=self._sort_orders[sort],
                                     exclude_tags=self.exclude_tags)
        threads: list[str] = []
        message_count = 0
        for thread in itertools.islice(thread_iterator, limit or None):
            threads.append(thread.threadid)
            message_count += thread.matched
        return iter(threads), message_count

    def add_message(self, path: str, tags: list[str] | None = None,
                    afterwards: Callable[[], None] | None = None) -> None:
        """
        Adds a file to the notmuch index.

        :param path: path to the file
        :param tags: tagstrings to add
        :param afterwards: callback to trigger after adding
        """
        tags = tags or []

        if self.ro:
            raise DatabaseROError()
        if self.path is None or not is_subdir_of(path, self.path):
            msg = 'message path %s ' % path
            msg += ' is not below notmuchs '
            msg += 'root path (%s)' % self.path
            raise DatabaseError(msg)
        else:
            self.writequeue.append(('add', afterwards, path, tags))

    def remove_message(self, message: Message,
                       afterwards: Callable[[], None] | None = None) -> None:
        """
        Remove a message from the notmuch index

        :param message: message to remove
        :param afterwards: callback to trigger after removing
        """
        if self.ro:
            raise DatabaseROError()
        path = message.get_filename()
        self.writequeue.append(('remove', afterwards, path))

    def save_named_query(self, alias: str, querystring: str,
                         afterwards: Callable[[], None] | None = None) -> None:
        """
        add an alias for a query string.

        These are stored in the notmuch database and can be used as part of
        more complex queries using the syntax "query:alias".
        See :manpage:`notmuch-search-terms(7)` for more info.

        :param alias: name of shortcut
        :param querystring: value, i.e., the full query string
        :param afterwards: callback to trigger after adding the alias
        """
        if self.ro:
            raise DatabaseROError()
        self.writequeue.append(('setconfig', afterwards, 'query.' + alias,
                                querystring))

    def remove_named_query(self, alias: str,
                           afterwards: Callable[[], None] | None = None) -> None:
        """
        remove a named query from the notmuch database.

        :param alias: name of shortcut
        :param afterwards: callback to trigger after adding the alias
        """
        if self.ro:
            raise DatabaseROError()
        self.writequeue.append(('setconfig', afterwards, 'query.' + alias, ''))
