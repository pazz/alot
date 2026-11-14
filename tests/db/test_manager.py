# Copyright (C) 2018 Patrick Totzke
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Test suite for alot.db.manager module."""

import os
import shutil
import tempfile
import textwrap
from unittest import mock

from alot.db.errors import NonexistantObjectError
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
        # a thread whose newer reply does not match tag:inbox
        for name, headers in [
                ('first', 'Message-ID: <first@example.com>\n'
                          'Date: Mon, 01 Jan 2024 10:00:00 +0000\n'),
                ('reply', 'Message-ID: <reply@example.com>\n'
                          'In-Reply-To: <first@example.com>\n'
                          'Date: Wed, 03 Jan 2024 10:00:00 +0000\n')]:
            path = os.path.join(cls.dbpath, name)
            with open(path, 'w') as f:
                f.write(headers + 'Subject: thread\n\nbody\n')
            msg, _ = cls.db.add(path)
            if name == 'first':
                msg.tags.add('inbox')
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

    @mock.patch('alot.db.thread.settings',
                **{'get.return_value': 'notmuch'})
    def test_thread_dates_from_matching_messages(self, _):
        tids, _ = self.manager.get_threads('tag:inbox')
        tid = next(tids)
        thread = self.manager.get_thread(tid, 'tag:inbox')
        self.assertEqual(thread.get_newest_date(),
                         thread.get_oldest_date())
        self.assertEqual(thread.get_total_messages(), 2)
        # the whole thread without a query, or when it no longer matches
        for query in ['', '*', 'tag:nosuchtag']:
            thread = self.manager.get_thread(tid, query)
            self.assertGreater(thread.get_newest_date(),
                               thread.get_oldest_date())

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
