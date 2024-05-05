# Copyright (C) 2018 Patrick Totzke
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Test suite for alot.db.manager module."""

import os
import shutil
import tempfile
import textwrap
from unittest import mock

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
        cls.db.close()
        cls.manager = DBManager(cls.dbpath)

        # clean up temporary database
        cls.addClassCleanup(shutil.rmtree, cls.dbpath)

        # let global settings manager read our temporary notmuch config
        settings.read_notmuch_config(cls.notmuch_config_path)

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
