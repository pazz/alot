# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from collections import deque
import contextlib
import logging

from notmuch2 import Database, NotmuchError, XapianError
import notmuch2

from .errors import DatabaseError
from .errors import DatabaseLockedError
from .errors import DatabaseROError
from .errors import NonexistantObjectError
from .message import Message
from .thread import Thread
from .utils import is_subdir_of
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

    def __init__(self, path=None, ro=False):
        """
        :param path: absolute path to the notmuch index
        :type path: str
        :param ro: open the index in read-only mode
        :type ro: bool
        """
        self.ro = ro
        self.path = path
        self.writequeue = deque([])
        self.processes = []

    def flush(self):
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
                    # the first two coordinants are cnmdname and post-callback
                    cmd, afterwards = current_item[:2]
                    logging.debug('cmd created')

                    # acquire a writeable db handler
                    try:
                        mode = Database.MODE.READ_WRITE
                        db = Database(path=self.path, mode=mode)
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
                            for msg in db.messages(querystring):
                                with msg.frozen():
                                    if cmd == 'toggle':
                                        to_remove = []
                                        to_add = []
                                        for tag in tags:
                                            if tag in msg.tags:
                                                to_remove.append(tag)
                                            else:
                                                to_add.append(tag)
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

    def tag(self, querystring, tags, afterwards=None, remove_rest=False):
        """
        add tags to messages matching `querystring`.
        This appends a tag operation to the write queue and raises
        :exc:`~errors.DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :type querystring: str
        :param tags: a list of tags to be added
        :type tags: list of str
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :type afterwards: callable
        :param remove_rest: remove tags from matching messages before tagging
        :type remove_rest: bool
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

    def untag(self, querystring, tags, afterwards=None):
        """
        removes tags from messages that match `querystring`.
        This appends an untag operation to the write queue and raises
        :exc:`~errors.DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :type querystring: str
        :param tags: a list of tags to be added
        :type tags: list of str
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :type afterwards: callable
        :exception: :exc:`~errors.DatabaseROError`

        .. note::
            This only adds the requested operation to the write queue.
            You need to call :meth:`DBManager.flush` to actually write out.
        """
        if self.ro:
            raise DatabaseROError()
        self.writequeue.append(('untag', afterwards, querystring, tags))

    def toggle_tags(self, querystring, tags, afterwards=None):
        """
        toggles tags from messages that match `querystring`.
        This appends a toggle operation to the write queue and raises
        :exc:`~errors.DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :type querystring: str
        :param tags: a list of tags to be added
        :type tags: list of str
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :type afterwards: callable
        :exception: :exc:`~errors.DatabaseROError`

        .. note::
            This only adds the requested operation to the write queue.
            You need to call :meth:`DBManager.flush` to actually write out.
        """
        if self.ro:
            raise DatabaseROError()
        self.writequeue.append(('toggle', afterwards, querystring, tags))

    def count_messages(self, querystring):
        """returns number of messages that match `querystring`"""
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY)
        return db.count_messages(querystring,
                                 exclude_tags=settings.get('exclude_tags'))

    def count_threads(self, querystring):
        """returns number of threads that match `querystring`"""
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY)
        return db.count_threads(querystring,
                                exclude_tags=settings.get('exclude_tags'))

    @contextlib.contextmanager
    def _with_notmuch_thread(self, tid):
        """returns :class:`notmuch2.Thread` with given id"""
        with Database(path=self.path, mode=Database.MODE.READ_ONLY) as db:
            try:
                yield next(db.threads('thread:' + tid))
            except NotmuchError:
                errmsg = 'no thread with id %s exists!' % tid
                raise NonexistantObjectError(errmsg)

    def get_thread(self, tid):
        """returns :class:`Thread` with given thread id (str)"""
        with self._with_notmuch_thread(tid) as thread:
            return Thread(self, thread)

    @contextlib.contextmanager
    def _with_notmuch_message(self, mid):
        """returns :class:`notmuch2.Message` with given id"""
        mode = Database.MODE.READ_ONLY
        with Database(path=self.path, mode=mode) as db:
            try:
                yield db.find_message(mid)
            except:
                errmsg = 'no message with id %s exists!' % mid
                raise NonexistantObjectError(errmsg)

    def get_message(self, mid):
        """returns :class:`Message` with given message id (str)"""
        with self._with_notmuch_message(mid) as msg:
            return Message(self, msg)

    def get_all_tags(self):
        """
        returns all tagsstrings used in the database
        :rtype: list of str
        """
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY)
        return [t for t in db.tags]

    def get_named_queries(self):
        """
        returns the named queries stored in the database.
        :rtype: dict (str -> str) mapping alias to full query string
        """
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY)
        return {k[6:]: db.config[k] for k in db.config
                                    if k.startswith('query.')}

    def get_threads(self, querystring, sort='newest_first', exclude_tags=None):
        """
        asynchronously look up thread ids matching `querystring`.

        :param querystring: The query string to use for the lookup
        :type querystring: str.
        :param sort: Sort order. one of ['oldest_first', 'newest_first',
                     'message_id', 'unsorted']
        :type query: str
        :param exclude_tags: Tags to exclude by default unless included in the
                             search
        :type exclude_tags: list of str
        :returns: a pipe together with the process that asynchronously
                  writes to it.
        :rtype: (:class:`multiprocessing.Pipe`,
                :class:`multiprocessing.Process`)
        """
        assert sort in self._sort_orders
        db = Database(path=self.path, mode=Database.MODE.READ_ONLY)
        for t in db.threads(querystring,
                            sort=self._sort_orders[sort],
                            exclude_tags=settings.get('exclude_tags')):
            yield t.threadid

    def add_message(self, path, tags=None, afterwards=None):
        """
        Adds a file to the notmuch index.

        :param path: path to the file
        :type path: str
        :param tags: tagstrings to add
        :type tags: list of str
        :param afterwards: callback to trigger after adding
        :type afterwards: callable or None
        """
        tags = tags or []

        if self.ro:
            raise DatabaseROError()
        if not is_subdir_of(path, self.path):
            msg = 'message path %s ' % path
            msg += ' is not below notmuchs '
            msg += 'root path (%s)' % self.path
            raise DatabaseError(msg)
        else:
            self.writequeue.append(('add', afterwards, path, tags))

    def remove_message(self, message, afterwards=None):
        """
        Remove a message from the notmuch index

        :param message: message to remove
        :type message: :class:`Message`
        :param afterwards: callback to trigger after removing
        :type afterwards: callable or None
        """
        if self.ro:
            raise DatabaseROError()
        path = message.get_filename()
        self.writequeue.append(('remove', afterwards, path))

    def save_named_query(self, alias, querystring, afterwards=None):
        """
        add an alias for a query string.

        These are stored in the notmuch database and can be used as part of
        more complex queries using the syntax "query:alias".
        See :manpage:`notmuch-search-terms(7)` for more info.

        :param alias: name of shortcut
        :type alias: str
        :param querystring: value, i.e., the full query string
        :type querystring: str
        :param afterwards: callback to trigger after adding the alias
        :type afterwards: callable or None
        """
        if self.ro:
            raise DatabaseROError()
        self.writequeue.append(('setconfig', afterwards, 'query.' + alias,
                                querystring))

    def remove_named_query(self, alias, afterwards=None):
        """
        remove a named query from the notmuch database.

        :param alias: name of shortcut
        :type alias: str
        :param afterwards: callback to trigger after adding the alias
        :type afterwards: callable or None
        """
        if self.ro:
            raise DatabaseROError()
        self.writequeue.append(('setconfig', afterwards, 'query.' + alias, ''))
