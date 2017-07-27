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
from alot.settings.errors import ConfigError, NoMatchingAccount

from .. import utilities


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


class TestSettingsManagerGetAccountByAddress(utilities.TestCaseClassCleanup):
    """Test the get_account_by_address helper."""

    @classmethod
    def setUpClass(cls):
        config = textwrap.dedent("""\
            [accounts]
                [[default]]
                    realname = That Guy
                    address = that_guy@example.com
                    sendmail_commnd = /bin/true

                [[other]]
                    realname = A Dude
                    address = a_dude@example.com
                    sendmail_command = /bin/true
            """)

        # Allow settings.reload to work by not deleting the file until the end
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(config)
        cls.addClassCleanup(os.unlink, f.name)

        # Replace the actual settings object with our own using mock, but
        # ensure it's put back afterwards
        cls.manager = SettingsManager(alot_rc=f.name)

    def test_exists_addr(self):
        acc = self.manager.get_account_by_address('that_guy@example.com')
        self.assertEqual(acc.realname, 'That Guy')

    def test_doesnt_exist_return_default(self):
        acc = self.manager.get_account_by_address('doesntexist@example.com',
                                                  return_default=True)
        self.assertEqual(acc.realname, 'That Guy')

    def test_doesnt_exist_raise(self):
        with self.assertRaises(NoMatchingAccount):
            self.manager.get_account_by_address('doesntexist@example.com')

    def test_doesnt_exist_no_default(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write('')
            settings = SettingsManager(alot_rc=f.name)
        with self.assertRaises(NoMatchingAccount):
            settings.get_account_by_address('that_guy@example.com',
                                            return_default=True)
