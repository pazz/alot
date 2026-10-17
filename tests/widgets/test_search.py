# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from datetime import datetime
import unittest
from unittest import mock
import warnings

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


class TestThreadlineWidget(unittest.TestCase):

    @mock.patch('alot.widgets.globals.settings')
    @mock.patch('alot.widgets.search.settings')
    def test_tag_widgets_are_collected(self, settings, tag_settings):
        settings.get_threadline_theming.return_value = {
            'parts': ['tags'], 'normal': None, 'focus': None,
            'tags': {'width': ('fit', 0, 0), 'normal': None, 'focus': None}}
        tag_settings.get_tagstring_representation.side_effect = \
            lambda tag, *_: {'translated': tag, 'normal': None,
                             'focussed': None}
        dbman = mock.Mock()
        dbman.get_thread.return_value.get_tags.return_value = ['b', 'a']
        widget = search.ThreadlineWidget('tid', dbman)
        self.assertEqual([w.tag for w in widget.widgets], ['a', 'b'])

    @mock.patch('alot.widgets.globals.settings')
    @mock.patch('alot.widgets.search.settings')
    def test_weighted_tags_are_aligned(self, settings, tag_settings):
        settings.get_threadline_theming.return_value = {
            'parts': ['tags'], 'normal': None, 'focus': None,
            'tags': {'width': ('weight', 1), 'alignment': 'right',
                     'normal': None, 'focus': None}}
        tag_settings.get_tagstring_representation.side_effect = \
            lambda tag, *_: {'translated': tag, 'normal': None,
                             'focussed': None}
        dbman = mock.Mock()
        dbman.get_thread.return_value.get_tags.return_value = ['b', 'a']
        widget = search.ThreadlineWidget('tid', dbman)
        self.assertEqual(widget.render((6,)).text, [b'   a b'])
        # too narrow: tags that do not fit are dropped, not cut, and urwid
        # does not warn (on the terminal)
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            self.assertEqual(widget.render((2,)).text, [b'a '])


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

    def test_fit_column_without_maximum(self):
        # the theme's default width for a part without one
        thread = mock.Mock(**{'get_subject.return_value': 'a subject'})
        struct = {'width': ('fit', 0, 0), 'alignment': 'left',
                  'normal': None, 'focus': None}
        width, widget = search.build_text_part('subject', thread, struct)
        self.assertEqual(width, 9)

    def test_weight_column(self):
        thread = mock.Mock(**{'get_subject.return_value': 'a subject'})
        struct = {'width': ('weight', 1), 'alignment': 'left',
                  'normal': None, 'focus': None}
        _, widget = search.build_text_part('subject', thread, struct)
        self.assertEqual(widget.render((9,)).text, [b'a subject'])

    def test_weight_column_alignment(self):
        thread = mock.Mock(**{'get_subject.return_value': 'subj'})
        struct = {'width': ('weight', 1), 'alignment': 'right',
                  'normal': None, 'focus': None}
        _, widget = search.build_text_part('subject', thread, struct)
        self.assertEqual(widget.render((6,)).text, [b'  subj'])

    def test_fit_column_keeps_start_of_wide_content(self):
        # double-width content is cut to maxw columns at its end
        thread = mock.Mock(**{'get_subject.return_value': '山田太郎'})
        struct = {'width': ('fit', 0, 4), 'alignment': 'right',
                  'normal': None, 'focus': None}
        width, widget = search.build_text_part('subject', thread, struct)
        self.assertEqual(widget.render((width,)).text,
                         ['山田'.encode()])

    def test_wrap_column(self):
        thread = mock.Mock(**{'get_subject.return_value': 'aaa bbb ccc ddd'})
        struct = {'width': ('wrap', 0, 7, 3, 2), 'alignment': 'left',
                  'normal': None, 'focus': None}
        width, widget = search.build_text_part('subject', thread, struct)
        self.assertEqual(width, 7)
        self.assertEqual(widget.render((7,)).text,
                         [b'aaa bbb', b'ccc ddd', b'       '])
