# Copyright (C) 2018 Patrick Totzke
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Test suite for alot.db.manager module."""

import asyncio
import contextlib
import os
import shutil
import tempfile
import textwrap
import threading
import time
from unittest import mock

from alot.commands.globals import FlushCommand
from alot.db.errors import DatabaseLockedError, NonexistantObjectError
from alot.db.manager import DBManager
from alot.settings.const import settings
from notmuch2 import Database

from .. import utilities


class TestDBManager(utilities.TestCaseClassCleanup):

    @classmethod
    def setUpClass(cls):

        # create temporary notmuch config
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = true
                """))
            cls.notmuch_config_path = f.name
        cls.addClassCleanup(os.unlink, f.name)

        # define an empty notmuch database in a temporary directory
        cls.dbpath = tempfile.mkdtemp()
        cls.db = Database.create(path=cls.dbpath)
        mail = os.path.join(cls.dbpath, 'mail')
        with open(mail, 'w') as f:
            f.write('Message-ID: <known@example.com>\nSubject: hi\n\nbody\n')
        cls.db.add(mail)
        cls.db.close()
        cls.manager = DBManager(cls.dbpath, config=Database.CONFIG.EMPTY)

        # clean up temporary database
        cls.addClassCleanup(shutil.rmtree, cls.dbpath)

        # let global settings manager read our temporary notmuch config
        settings.read_notmuch_config(cls.notmuch_config_path)

    def test_get_message(self):
        msg = self.manager.get_message('known@example.com')
        self.assertEqual(msg.get_message_id(), 'known@example.com')

    def test_get_unknown_message(self):
        with self.assertRaises(NonexistantObjectError):
            self.manager.get_message('unknown@example.com')

    def test_get_unknown_thread(self):
        with self.assertRaises(NonexistantObjectError):
            self.manager.get_thread('0000000000000000')

    def test_save_named_query(self):
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = true
                """))
        self.addCleanup(os.unlink, f.name)

        with mock.patch.dict('os.environ', NOTMUCH_CONFIG=f.name):
            alias = 'key'
            querystring = 'query string'
            self.manager.save_named_query(alias, querystring)
            self.manager.flush()

            named_queries_dict = self.manager.get_named_queries()
            self.assertDictEqual(named_queries_dict, {alias: querystring})

    def test_tag_skips_unchanged_messages(self):
        query = 'id:known@example.com OR id:unknown@example.com'
        tags = ['a b"c', 'd']

        def revision():
            with Database(self.dbpath, config=Database.CONFIG.EMPTY) as db:
                return db.revision().rev

        self.manager.tag(query, tags)
        self.manager.flush()
        msg = self.manager.get_message('known@example.com')
        self.assertTrue(set(tags) <= set(msg.get_tags()))
        before = revision()
        self.manager.tag(query, tags)
        self.manager.untag(query, ['e'])
        self.manager.flush()
        self.assertEqual(revision(), before)
        self.manager.untag(query, tags)
        self.manager.flush()
        msg = self.manager.get_message('known@example.com')
        self.assertFalse(set(tags) & set(msg.get_tags()))
        self.manager.tag('*', ['f'])  # a bare '*' still matches everything
        self.manager.flush()
        self.assertIn('f', self.manager.get_message('known@example.com').get_tags())


class TestFlushAsync(utilities.TestCaseClassCleanup):
    """#1365: writes run in a worker thread, so the interface keeps going"""

    @classmethod
    def setUpClass(cls):
        cls.dbpath = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls.dbpath)
        with Database.create(path=cls.dbpath) as db:
            for n in range(2):
                mail = os.path.join(cls.dbpath, 'mail%d' % n)
                with open(mail, 'w') as f:
                    f.write('Message-ID: <%d@example.com>\nSubject: hi\n\n'
                            'body\n' % n)
                db.add(mail)
        patcher = mock.patch('alot.db.manager.settings.get_notmuch_setting',
                             return_value=False)
        patcher.start()
        cls.addClassCleanup(patcher.stop)

    def setUp(self):
        # a new one per test, as its lock belongs to one event loop
        self.manager = DBManager(self.dbpath, config=Database.CONFIG.EMPTY)

    def tags(self, n):
        return self.manager.get_message('%d@example.com' % n).get_tags()

    @staticmethod
    def slow_atomic():
        atomic = Database.atomic

        @contextlib.contextmanager
        def slow(db):
            with atomic(db) as ctx:
                time.sleep(0.3)
                yield ctx
        return mock.patch.object(Database, 'atomic', slow)

    @utilities.async_test
    async def test_flush_command_keeps_the_event_loop_running(self):
        ticks = 0

        async def tick():
            nonlocal ticks
            while True:
                ticks += 1
                await asyncio.sleep(0.01)

        ui = mock.Mock(dbman=self.manager, db_was_locked=False)
        self.manager.tag('id:0@example.com', ['slow'])
        ticker = asyncio.create_task(tick())
        with self.slow_atomic():
            await FlushCommand().apply(ui)
        ticker.cancel()
        self.assertIn('slow', self.tags(0))
        self.assertGreater(ticks, 5)

    @utilities.async_test
    async def test_status_bar_counts_the_write_in_progress(self):
        ui = mock.Mock(dbman=self.manager, db_was_locked=False)
        counts = []
        ui.update.side_effect = lambda: counts.append(
            len(self.manager.writequeue))
        self.manager.tag('id:0@example.com', ['g'])
        with self.slow_atomic():
            flush = asyncio.create_task(FlushCommand().apply(ui))
            await asyncio.sleep(0.1)  # the worker thread is writing
            self.assertEqual(len(self.manager.writequeue), 1)
            await flush
        self.assertEqual(counts, [1, 0])  # before and after the write

    @utilities.async_test
    async def test_callbacks_run_in_the_event_loop(self):
        loop_thread = threading.get_ident()
        calls = []

        def callback(name):
            return lambda: calls.append((name, threading.get_ident()))

        self.manager.tag('id:0@example.com', ['a'], afterwards=callback('a'))
        first = asyncio.create_task(self.manager.flush_async())
        await asyncio.sleep(0)  # the first flush is writing
        self.manager.tag('id:1@example.com', ['b'], afterwards=callback('b'))
        with self.slow_atomic():
            await asyncio.gather(first, self.manager.flush_async())
        self.assertEqual(calls, [('a', loop_thread), ('b', loop_thread)])
        self.assertIn('a', self.tags(0))
        self.assertIn('b', self.tags(1))
        self.assertFalse(self.manager.writequeue)

    @utilities.async_test
    async def test_failed_write_stays_queued(self):
        callback = mock.Mock()
        self.manager.tag('id:0@example.com', ['c'], afterwards=callback)
        item = self.manager.writequeue[0]
        with mock.patch.object(self.manager, '_write',
                               side_effect=DatabaseLockedError):
            with self.assertRaises(DatabaseLockedError):
                await self.manager.flush_async()
        self.assertEqual(list(self.manager.writequeue), [item])
        callback.assert_not_called()
        await self.manager.flush_async()
        callback.assert_called_once_with()
        self.assertIn('c', self.tags(0))

    @utilities.async_test
    async def test_flush_leaves_the_queue_to_flush_async(self):
        # e.g. a hook calls flush() while flush_async waits for the index:
        # writing the next entry first could undo the order of tag, untag
        write = self.manager._write

        def slow_write(item):
            if 'd' in item[3] and item[0] == 'tag':
                time.sleep(0.3)  # waiting for the index
            write(item)

        self.manager.tag('id:0@example.com', ['d'])
        with mock.patch.object(self.manager, '_write', slow_write):
            writing = asyncio.create_task(self.manager.flush_async())
            await asyncio.sleep(0.1)  # the worker thread is waiting
            self.manager.untag('id:0@example.com', ['d'])
            self.manager.flush()
            await writing
        self.assertNotIn('d', self.tags(0))
        self.assertFalse(self.manager.writequeue)

    @utilities.async_test
    async def test_a_failed_write_is_not_overtaken(self):
        written = []
        write = self.manager._write

        def fail_first(item):
            time.sleep(0.1)
            if not written:
                written.append(None)
                raise DatabaseLockedError()
            written.append(item[3])
            write(item)

        self.manager.tag('id:0@example.com', ['f'])
        with mock.patch.object(self.manager, '_write', fail_first):
            first = asyncio.create_task(self.manager.flush_async())
            await asyncio.sleep(0)  # the first flush is writing
            self.manager.untag('id:0@example.com', ['f'])
            results = await asyncio.gather(
                first, self.manager.flush_async(), return_exceptions=True)
        self.assertIsInstance(results[0], DatabaseLockedError)
        self.assertEqual(written, [None, ['f'], ['f']])  # tag, then untag
        self.assertNotIn('f', self.tags(0))
