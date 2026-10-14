# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from datetime import datetime
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


class TestPrepareContentStringDates(unittest.TestCase):

    def test_messages_without_date_come_last(self):
        def msg(date, body):
            return mock.Mock(**{'get_date.return_value': date,
                                'get_body_text.return_value': body})
        msgs = [msg(None, 'undated'), msg(datetime(2024, 1, 2), 'newer'),
                msg(datetime(2024, 1, 1), 'older')]
        thread = mock.Mock(
            **{'get_messages.return_value': dict.fromkeys(msgs)})
        self.assertEqual(search.prepare_content_string(thread),
                         'newer older undated')


class TestBuildTextPart(unittest.TestCase):

    def test_zero_width_subject(self):
        # combining characters only, as in spam subjects; cut to 10 columns
        thread = mock.Mock(**{'get_subject.return_value': '\u0300' * 36})
        struct = {'width': ('fit', 0, 10), 'alignment': 'left',
                  'normal': None, 'focus': None}
        _, widget = search.build_text_part('subject', thread, struct)
        widget.render((10,))

    def test_weight_column(self):
        thread = mock.Mock(**{'get_subject.return_value': 'a subject'})
        struct = {'width': ('weight', 1), 'alignment': 'left',
                  'normal': None, 'focus': None}
        _, widget = search.build_text_part('subject', thread, struct)
        self.assertEqual(widget.render((9,)).text, [b'a subject'])

    def test_wrap_column(self):
        thread = mock.Mock(**{'get_subject.return_value': 'aaa bbb ccc ddd'})
        struct = {'width': ('wrap', 0, 7, 3, 2), 'alignment': 'left',
                  'normal': None, 'focus': None}
        width, widget = search.build_text_part('subject', thread, struct)
        self.assertEqual(width, 7)
        self.assertEqual(widget.render((7,)).text,
                         [b'aaa bbb', b'ccc ddd', b'       '])
