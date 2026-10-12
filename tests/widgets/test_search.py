# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

from alot.widgets import search


class TestPrepareDateString(unittest.TestCase):

    def test_thread_without_date(self):
        thread = mock.Mock(**{'get_newest_date.return_value': None})
        self.assertEqual(search.prepare_date_string(thread), ' ')


class TestPrepareContentString(unittest.TestCase):

    def test_quoted_lines_are_dropped(self):
        msg = mock.Mock(**{'get_body_text.return_value': '> quote\nreply'})
        thread = mock.Mock(**{'get_messages.return_value': {msg: []}})
        self.assertEqual(search.prepare_content_string(thread), 'reply')


class TestBuildTagsPart(unittest.TestCase):

    def test_no_visible_tags(self):
        self.assertEqual(search.build_tags_part([], None, None), (-1, None))
