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

    def test_read_config_doesnt_exist(self):
        """If there is not an alot config things don't break.

        This specifically tests for issue #1094, which is caused by the
        defaults not being loaded if there isn't an alot config files, and thus
        calls like `get_theming_attribute` fail with strange exceptions.
        """
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = true
                """))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager(notmuch_rc=f.name)

        manager.get_theming_attribute('global', 'body')

    def test_read_notmuch_config_doesnt_exist(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(textwrap.dedent("""\
                [accounts]
                    [[default]]
                        realname = That Guy
                        address = thatguy@example.com
                """))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager(alot_rc=f.name)

        setting = manager.get_notmuch_setting('foo', 'bar')
        self.assertIsNone(setting)


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

    def test_real_name_will_be_stripped_before_matching(self):
        acc = self.manager.get_account_by_address(
            'That Guy <a_dude@example.com>')
        self.assertEqual(acc.realname, 'A Dude')

    @unittest.expectedFailure
    def test_address_case(self):
        """Some servers do not differentiate addresses by case.

        So, for example, "foo@example.com" and "Foo@example.com" would be
        considered the same. Among servers that do this gmail, yahoo, fastmail,
        anything running Exchange (i.e., most large corporations), and others.
        """
        acc1 = self.manager.get_account_by_address('That_guy@example.com')
        acc2 = self.manager.get_account_by_address('that_guy@example.com')
        self.assertIs(acc1, acc2)
