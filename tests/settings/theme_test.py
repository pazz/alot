# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from __future__ import absolute_import

import unittest

from alot.settings import theme


DUMMY_THEME = """\
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
[search]
    focus = '', '', '', '', '', ''
    normal = '', '', '', '', '', ''
    [[threadline]]
        focus = '', '', '', '', '', ''
        normal = '', '', '', '', '', ''
[thread]
    arrow_bars = '', '', '', '', '', ''
    arrow_heads = '', '', '', '', '', ''
    attachment = '', '', '', '', '', ''
    attachment_focus = '', '', '', '', '', ''
    body = '', '', '', '', '', ''
    header = '', '', '', '', '', ''
    header_key = '', '', '', '', '', ''
    header_value = '', '', '', '', '', ''
    [[summary]]
        even = '', '', '', '', '', ''
        focus = '', '', '', '', '', ''
        odd = '', '', '', '', '', ''
"""


class TestThemeGetAttribute(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # We use a list of strings instead of a file path to pass in the config
        # file.  This is possible because the argument is handed to
        # configobj.ConfigObj directly and that accepts eigher:
        # http://configobj.rtfd.io/en/latest/configobj.html#reading-a-config-file
        cls.theme = theme.Theme(DUMMY_THEME.splitlines())

    def test_invalid_mode_raises_key_error(self):
        with self.assertRaises(KeyError) as cm:
            self.theme.get_attribute(0, 'mode does not exist',
                                     'name does not exist')
        self.assertTupleEqual(cm.exception.args, ('mode does not exist',))

    def test_invalid_name_raises_key_error(self):
        with self.assertRaises(KeyError) as cm:
            self.theme.get_attribute(0, 'global', 'name does not exist')
        self.assertTupleEqual(cm.exception.args, ('name does not exist',))

    # TODO tests for invalid part arguments.

    def test_invalid_colorindex_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.theme.get_attribute(0, 'global', 'body')
