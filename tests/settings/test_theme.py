# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import os
from unittest import TestCase, mock

from alot.settings import theme as module


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


class TestThemeGetAttribute(TestCase):

    @classmethod
    def setUpClass(cls):
        # We use a list of strings instead of a file path to pass in the config
        # file.  This is possible because the argument is handed to
        # configobj.ConfigObj directly and that accepts eigher:
        # https://configobj.rtfd.io/en/latest/configobj.html#reading-a-config-file
        cls.theme = module.Theme(DUMMY_THEME.splitlines())

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

class GetThemeTest(TestCase):
    def setUp(self):
        self.mock_os_path = mock.patch(
            "os.path", wraps=os.path
        ).start()
        self.mock_theme = mock.patch.object(
            module, 'Theme', spec_set=module.Theme
        ).start()
        self.addCleanup(mock.patch.stopall)

    def test_returns_theme_when_theme_found(self):
        self.mock_os_path.exists.return_value = True
        expected_theme = mock.sentinel
        self.mock_theme.return_value = expected_theme
        actual_theme = module.get_theme("test", "test.theme")
        self.assertEqual(expected_theme, actual_theme)

    def test_raises_config_error_when_theme_not_found(self):
        self.mock_os_path.exists.return_value = False
        with self.assertRaisesRegex(module.ConfigError, "Could not find theme test.theme"):
            module.get_theme("test", "test.theme")

    def test_raises_config_error_when_theme_fails_validation(self):
        self.mock_os_path.exists.return_value = True
        self.mock_theme.side_effect = module.ConfigError("test error")
        with self.assertRaisesRegex(
            module.ConfigError, 
            "Theme file `test/test.theme` failed validation: test error"
        ):
            module.get_theme("test", "test.theme")
