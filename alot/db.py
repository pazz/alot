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
    """cannot write to read-only database"""
    pass


class DatabaseLockedError(DatabaseError):
    """cannot write to locked index"""
    pass


class NonexistantObjectError(DatabaseError):
    """requested thread or message does not exist in the index"""
    pass


class FillPipeProcess(multiprocessing.Process):
    def __init__(self, it, pipe, fun=(lambda x: x)):
        multiprocessing.Process.__init__(self)
        self.it = it
        self.pipe = pipe[1]
        self.fun = fun

    def run(self):
        for a in self.it:
            self.pipe.send(self.fun(a))
        self.pipe.close()


class DBManager(object):
    """
    Keeps track of your index parameters, maintains a write-queue and
    lets you look up threads and messages directly to the persistent wrapper
    classes.
    """
    _sort_orders = {
        'oldest_first': notmuch.database.Query.SORT.OLDEST_FIRST,
        'newest_first': notmuch.database.Query.SORT.NEWEST_FIRST,
        'unsorted': notmuch.database.Query.SORT.UNSORTED,
        'message_id': notmuch.database.Query.SORT.MESSAGE_ID,
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
        :meth:`atomic <notmuch.Database.begin_atomic>` transaction.

        If this fails the current action is rolled back, stays in the write
        queue and an exception is raised.
        You are responsible to retry flushing at a later time if you want to
        ensure that the cached changes are applied to the database.

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
                cmd, querystring, tags, sync, afterwards = current_item
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
                else:
                    if callable(afterwards):
                        afterwards()

    def kill_search_processes(self):
        """
        terminate all search processes that originate from
        this managers :meth:`get_threads`.
        """
        for p in self.processes:
            p.terminate()
        self.processes = []

    def tag(self, querystring, tags, afterwards=None, remove_rest=False):
        """
        add tags to messages matching `querystring`.
        This appends a tag operation to the write queue and raises
        :exc:`DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :type querystring: str
        :param tags: a list of tags to be added
        :type tags: list of str
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :type afterwards: callable
        :param remove_rest: remove tags from matching messages before tagging
        :type remove_rest: bool
        :exception: :exc:`DatabaseROError`

        .. note::
            You need to call :meth:`DBManager.flush` to actually write out.
        """
        if self.ro:
            raise DatabaseROError()
        sync_maildir_flags = config.getboolean('maildir', 'synchronize_flags')
        if remove_rest:
            self.writequeue.append(('set', querystring, tags,
                                    sync_maildir_flags, afterwards))
        else:
            self.writequeue.append(('tag', querystring, tags,
                                    sync_maildir_flags, afterwards))

    def untag(self, querystring, tags, afterwards=None):
        """
        removes tags from messages that match `querystring`.
        This appends an untag operation to the write queue and raises
        :exc:`DatabaseROError` if in read only mode.

        :param querystring: notmuch search string
        :type querystring: str
        :param tags: a list of tags to be added
        :type tags: list of str
        :param afterwards: callback that gets called after successful
                           application of this tagging operation
        :type afterwards: callable
        :exception: :exc:`DatabaseROError`

        .. note::
            You need to call :meth:`DBManager.flush` to actually write out.
        """
        if self.ro:
            raise DatabaseROError()
        sync_maildir_flags = config.getboolean('maildir', 'synchronize_flags')
        self.writequeue.append(('untag', querystring, tags,
                                sync_maildir_flags, afterwards))

    def count_messages(self, querystring):
        """returns number of messages that match `querystring`"""
        return self.query(querystring).count_messages()

    def search_thread_ids(self, querystring):
        """
        returns the ids of all threads that match the `querystring`
        This copies! all integer thread ids into an new list.

        :returns: list of str
        """

        return self.query_threaded(querystring)

    def _get_notmuch_thread(self, tid):
        """returns :class:`notmuch.database.Thread` with given id"""
        query = self.query('thread:' + tid)
        try:
            return query.search_threads().next()
        except StopIteration:
            errmsg = 'no thread with id %s exists!' % tid
            raise NonexistantObjectError(errmsg)

    def get_thread(self, tid):
        """returns :class:`Thread` with given thread id (str)"""
        return Thread(self, self._get_notmuch_thread(tid))

    def _get_notmuch_message(self, mid):
        """returns :class:`notmuch.database.Message` with given id"""
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        try:
            return db.find_message(mid)
        except:
            errmsg = 'no message with id %s exists!' % mid
            raise NonexistantObjectError(errmsg)

    def get_message(self, mid):
        """returns :class:`Message` with given message id (str)"""
        return Message(self, self._get_notmuch_message(mid))

    def get_all_tags(self):
        """
        returns all tagsstrings used in the database
        :rtype: list of str
        """
        db = Database(path=self.path)
        return [t for t in db.get_all_tags()]

    def async(self, cbl, fun):
        """
        return a pair (pipe, process) so that the process writes
        `fun(a)` to the pipe for each element `a` in the iterable returned
        by the callable `cbl`.

        :param cbl: a function returning something iterable
        :type cbl: callable
        :param fun: an unary translation function
        :type fun: callable
        :rtype: (:class:`multiprocessing.Pipe`,
                :class:`multiprocessing.Process`)
        """
        pipe = multiprocessing.Pipe(False)
        receiver, sender = pipe
        process = FillPipeProcess(cbl(), pipe, fun)
        process.start()
        self.processes.append(process)
        # closing the sending end in this (receiving) process guarantees
        # that here the apropriate EOFError is raised upon .recv in the walker
        sender.close()
        return receiver, process

    def get_threads(self, querystring, sort='newest_first'):
        """
        asynchronously look up thread ids matching `querystring`.

        :param querystring: The query string to use for the lookup
        :type querystring: str.
        :param sort: Sort order. one of ['oldest_first', 'newest_first',
                     'message_id', 'unsorted']
        :type query: str
        :returns: a pipe together with the process that asynchronously
                  writes to it.
        :rtype: (:class:`multiprocessing.Pipe`,
                :class:`multiprocessing.Process`)
        """
        assert sort in self._sort_orders.keys()
        q = self.query(querystring)
        q.set_sort(self._sort_orders[sort])
        return self.async(q.search_threads, (lambda a: a.get_thread_id()))

    def query(self, querystring):
        """
        creates :class:`notmuch.Query` objects on demand

        :param querystring: The query string to use for the lookup
        :type query: str.
        :returns: :class:`notmuch.Query` -- the query object.
        """
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return db.create_query(querystring)

    def add_message(self, path):
        """
        Adds a file to the notmuch index.

        :param path: path to the file
        :type path: str
        :returns: the message object corresponding the added message
        :rtype: :class:`alot.message.Message`
        """
        db = Database(path=self.path, mode=Database.MODE.READ_WRITE)
        try:
            message, status = db.add_message(path,
                                             sync_maildir_flags=True)
        except NotmuchError as e:
            raise DatabaseError(unicode(e))

        return Message(self, message)

    def remove_message(self, message):
        """
        Remove a message from the notmuch index

        :param message: message to remove
        :type message: :class:`Message`
        """
        path = message.get_filename()
        db = Database(path=self.path, mode=Database.MODE.READ_WRITE)
        try:
            db.remove_message(path)
        except NotmuchError as e:
            raise DatabaseError(unicode(e))


class Thread(object):
    """
    A wrapper around a notmuch mailthread (:class:`notmuch.database.Thread`)
    that ensures persistence of the thread: It can be safely read multiple
    times, its manipulation is done via a :class:`DBManager` and it
    can directly provide contained messages as :class:`~alot.message.Message`.
    """

    def __init__(self, dbman, thread):
        """
        :param dbman: db manager that is used for further lookups
        :type dbman: :class:`DBManager`
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
            :class:`DBManager's <DBManager>` write queue.
            You need to call :meth:`DBManager.flush` to actually write out.

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
                self._tags = tags
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
            :class:`DBManager's <DBManager>` write queue.
            You need to call :meth:`DBManager.flush` to actually write out.

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

    def get_authors(self):  # TODO: make this return a list of strings
        """returns authors string"""
        return self._authors

    def get_subject(self):
        """returns subject string"""
        return self._subject

    def get_toplevel_messages(self):
        """
        returns all toplevel messages contained in this thread.
        This are all the messages without a parent message
        (identified by 'in-reply-to' or 'references' header.

        :rtype: list of :class:`~alot.message.Message`
        """
        if not self._messages:
            self.get_messages()
        return self._toplevel_messages

    def get_messages(self):
        """
        returns all messages in this thread as dict mapping all contained
        messages to their direct responses.

        :rtype: dict mapping :class:`~alot.message.Message` to a list of
                :class:`~alot.message.Message`.
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
        :type msg: :class:`~alot.message.Message`
        :returns: list of :class:`~alot.message.Message` or `None`
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
