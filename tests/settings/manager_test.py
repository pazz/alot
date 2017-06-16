# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Test suite for alot.settings.manager module."""

from __future__ import absolute_import

import unittest

from alot.settings.manager import SettingsManager
from alot.settings.errors import ConfigError


class TestSettingsManager(unittest.TestCase):

    def test_reading_synchronize_flags_from_notmuch_config(self):
        config = [
            '[maildir]',
            'synchronize_flags = true',
        ]
        manager = SettingsManager()
        manager.read_notmuch_config(config)
        actual = manager.get_notmuch_setting('maildir', 'synchronize_flags')
        self.assertTrue(actual)

    def test_parsing_notmuch_config_with_non_bool_synchronize_flag_fails(self):
        config = [
            '[maildir]',
            'synchronize_flags = not bool'
        ]
        manager = SettingsManager()
        with self.assertRaises(ConfigError):
            manager.read_notmuch_config(config)
