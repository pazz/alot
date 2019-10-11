# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from urwid import AttrSpec
from unittest import mock

from alot.settings.const import settings
from alot.settings import theme
from alot.widgets.colour_text import parse_quotes


DUMMY_THEME_STRING = """\
[bufferlist]
    line = '', '', '', '', '', ''
    line_even = '', '', '', '', '', ''
    line_focus = '', '', '', '', '', ''
    line_odd = '', '', '', '', '', ''
[envelope]
    body = '', '', '', '', '', ''
    header = '', '', '', '', '', ''
    header_key = '', '', '', '', '', ''
    header_value = '', '', '', '', '', ''
[global]
    body = '', '', '', '', '', ''
    footer = '', '', '', '', '', ''
    notify_error = '', '', '', '', '', ''
    notify_normal = '', '', '', '', '', ''
    prompt = '', '', '', '', '', ''
    tag = '', '', '', '', '', ''
    tag_focus = '', '', '', '', '', ''
[help]
    section = '', '', '', '', '', ''
    text = '', '', '', '', '', ''
    title = '', '', '', '', '', ''
[taglist]
    line_even = '', '', '', '', '', ''
    line_focus = '', '', '', '', '', ''
    line_odd = '', '', '', '', '', ''
[namedqueries]
    line_even = '', '', '', '', '', ''
    line_focus = '', '', '', '', '', ''
    line_odd = '', '', '', '', '', ''
[search]
    focus = '', '', '', '', '', ''
    normal = '', '', '', '', '', ''
    [[threadline]]
        focus = '', '', '', '', '', ''
        normal = '', '', '', '', '', ''
[thread]
    quote_level_2 = '', '', '', '', '#201', '#202'
    quote_level_3 = '', '', '', '', '#301', '#302'
    quote_level_4 = '', '', '', '', '#401', '#402'
    quote_level_5 = '', '', '', '', '#501', '#502'
    quote_level_7 = '', '', '', '', '#701', '#702'
    arrow_bars = '', '', '', '', '', ''
    arrow_heads = '', '', '', '', '', ''
    attachment = '', '', '', '', '', ''
    attachment_focus = '', '', '', '', '', ''
    body = '', '', '', '', 'h102', 'h103'
    header = '', '', '', '', '', ''
    header_key = '', '', '', '', '', ''
    header_value = '', '', '', '', '', ''
    [[summary]]
        even = '', '', '', '', '', ''
        focus = '', '', '', '', '', ''
        odd = '', '', '', '', '', ''
"""

DUMMY_THEME = theme.Theme(DUMMY_THEME_STRING.splitlines())

SETTINGS = {'quote_symbol': '>',
            'colourmode': 256
            }

SETTINGS_test_symbol_regex = {'quote_symbol': '([Aa]|<>.b|>)',
                              'colourmode': 256
                              }


class TestQuoteLevel(unittest.TestCase):

    @mock.patch(
        'alot.commands.globals.settings._config', SETTINGS)
    @mock.patch(
        'alot.commands.globals.settings._theme', DUMMY_THEME)
    def test_quote_level_get_equals_corresponding_attribute(self):
        self.assertEqual(parse_quotes('> >>'), AttrSpec('#301', '#302'))
        self.assertEqual(parse_quotes('>> >> >> >'), AttrSpec('#701', '#702'))

        # Higest level quote possible matched
        self.assertEqual(parse_quotes('>> >> >> >>'), AttrSpec('#701', '#702'))

    @mock.patch(
        'alot.commands.globals.settings._config', SETTINGS_test_symbol_regex)
    @mock.patch(
        'alot.commands.globals.settings._theme', DUMMY_THEME)
    def test_quote_undefined_or_no_quote_equals_none(self):
        self.assertIsNone(parse_quotes(''))
        self.assertIsNone(parse_quotes('test no quote'))
        self.assertIsNone(parse_quotes('>> >> >>'))

        # Undefined quote level
        self.assertIsNone(parse_quotes('>'))

    @mock.patch(
        'alot.commands.globals.settings._config', SETTINGS_test_symbol_regex)
    @mock.patch(
        'alot.commands.globals.settings._theme', DUMMY_THEME)
    def test_regex_symbol_is_correct(self):
        # Match 4th level quote
        self.assertEqual(parse_quotes('Aaa A'), AttrSpec('#401', '#402'))

        self.assertIsNone(parse_quotes('One symbol at the end <>!b'))
        self.assertEqual(parse_quotes('Aa<>tb Ah, so much fun'), AttrSpec('#401', '#402'))
        self.assertEqual(parse_quotes('> A symbol at the begining'), AttrSpec('#201', '#202'))
        self.assertEqual(parse_quotes('A A symbols every> where>>! >>'), AttrSpec('#201', '#202'))
        self.assertEqual(parse_quotes('A>A or A<A ?'), AttrSpec('#301', '#302'))
