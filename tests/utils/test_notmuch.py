# encoding=utf-8

# SPDX-FileCopyrightText: 2020 Kirill Elagin <https://kir.elagin.me/>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for alot.utils.notmuch"""

import unittest
from unittest import mock

import os.path

from alot.utils import notmuch

# Good descriptive test names often don't fit PEP8, which is meant to cover
# functions meant to be called by humans.
# pylint: disable=invalid-name


class MockSettings:
    def __init__(self, database_path):
        self._database_path = database_path

    def get_notmuch_setting(self, section, key):
        if section == 'database' and key == 'path':
            return self._database_path
        else:
            return None

db_path_rel = os.path.join('path', 'to', 'db')
home = os.path.abspath(os.path.join(os.path.sep, 'home', 'someuser'))
maildir = os.path.abspath(os.path.join(os.path.sep, 'var', 'mail'))

class TestFindDb(unittest.TestCase):
    """Tests for the find_db function."""

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_absolute_path(self):
        db_path_abs = os.path.abspath(os.path.join(os.path.sep, db_path_rel))
        settings = MockSettings(db_path_abs)
        self.assertEqual(notmuch.find_db(settings), db_path_abs)

    @mock.patch.dict(os.environ, {'HOME': home}, clear=True)
    def test_relative_path(self):
        settings = MockSettings(db_path_rel)
        self.assertEqual(notmuch.find_db(settings), os.path.join(home, db_path_rel))

    @mock.patch.dict(os.environ, {'MAILDIR': maildir}, clear=True)
    def test_maildir(self):
        settings = MockSettings(None)
        self.assertEqual(notmuch.find_db(settings), maildir)

    @mock.patch.dict(os.environ, {'HOME': home}, clear=True)
    def test_home_mail(self):
        settings = MockSettings(None)
        self.assertEqual(notmuch.find_db(settings), os.path.join(home, 'mail'))


    # Additional tests to make sure we closely replicate the behaviour
    # of notmuch even if the user’s environment is weird/wrong.

    @mock.patch.dict(os.environ, {'HOME': home, 'MAILDIR': ''}, clear=True)
    def test_empty_maildir(self):
        """Empty maildir should not be treated as unset."""
        settings = MockSettings(None)
        self.assertEqual(notmuch.find_db(settings), '')
