# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Test suite for alot.settings.manager module."""

from __future__ import absolute_import

import os
import tempfile
import textwrap
import unittest

from alot.settings.manager import SettingsManager
from alot.settings.errors import ConfigError


class TestSettingsManager(unittest.TestCase):

    def test_reading_synchronize_flags_from_notmuch_config(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = true
                """))
        self.addCleanup(os.unlink, f.name)

        manager = SettingsManager(notmuch_rc=f.name)
        actual = manager.get_notmuch_setting('maildir', 'synchronize_flags')
        self.assertTrue(actual)

    def test_parsing_notmuch_config_with_non_bool_synchronize_flag_fails(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = not bool
                """))
        self.addCleanup(os.unlink, f.name)

        with self.assertRaises(ConfigError):
            SettingsManager(notmuch_rc=f.name)

    def test_reload_notmuch_config(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = false
                """))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager(notmuch_rc=f.name)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = true
                """))
        self.addCleanup(os.unlink, f.name)

        manager.notmuch_rc_path = f.name
        manager.reload()
        actual = manager.get_notmuch_setting('maildir', 'synchronize_flags')
        self.assertTrue(actual)
