# encoding=utf-8
# Copyright © 2016 Dylan Baker

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for the alot.db.thread module."""
import datetime
import unittest
from unittest import mock

from alot.db import thread


class TestThreadGetAuthor(unittest.TestCase):

    __patchers = []

    @classmethod
    def setUpClass(cls):
        get_messages = []
        for a, d in [('foo', datetime.datetime(datetime.MINYEAR, 1, day=21)),
                     ('bar', datetime.datetime(datetime.MINYEAR, 1, day=17)),
                     ('foo', datetime.datetime(datetime.MINYEAR, 1, day=14)),
                     ('arf', datetime.datetime(datetime.MINYEAR, 1, 1, hour=1,
                                               minute=5)),
                     ('oof', datetime.datetime(datetime.MINYEAR, 1, 1, hour=1,
                                               minute=10)),
                     ('ooh', None)]:
            m = mock.Mock()
            m.get_date = mock.Mock(return_value=d)
            m.get_author = mock.Mock(return_value=a)
            get_messages.append(m)
        gm = mock.Mock()
        gm.keys = mock.Mock(return_value=get_messages)

        cls.__patchers.extend([
            mock.patch('alot.db.thread.Thread.get_messages',
                       new=mock.Mock(return_value=gm)),
            mock.patch('alot.db.thread.Thread.refresh', new=mock.Mock()),
        ])

        for p in cls.__patchers:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in reversed(cls.__patchers):
            p.stop()

    def setUp(self):
        # values are cached and each test needs it's own instance.
        self.thread = thread.Thread(mock.Mock(), mock.Mock())

    def test_default(self):
        self.assertEqual(
            self.thread.get_authors(),
            ['arf', 'oof', 'foo', 'bar', 'ooh'])

    def test_latest_message(self):
        with mock.patch('alot.db.thread.settings.get',
                        mock.Mock(return_value='latest_message')):
            self.assertEqual(
                self.thread.get_authors(),
                ['arf', 'oof', 'bar', 'foo', 'ooh'])
