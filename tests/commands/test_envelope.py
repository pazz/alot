# encoding=utf-8
# Copyright © 2017-2018 Dylan Baker

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for the alot.commands.envelope module."""

import email
import os
import tempfile
import textwrap
import unittest
from unittest import mock

from alot.commands import envelope
from alot.db.envelope import Envelope
from alot.errors import GPGProblem
from alot.settings.errors import NoMatchingAccount
from alot.settings.manager import SettingsManager
from alot.account import Account

from .. import utilities

# When using an assert from a mock a TestCase method might not use self. That's
# okay.
# pylint: disable=no-self-use


class TestAttachCommand(unittest.TestCase):
    """Tests for the AttachCommaned class."""

    def test_single_path(self):
        """A test for an existing single path."""
        ui = utilities.make_ui()

        with tempfile.TemporaryDirectory() as d:
            testfile = os.path.join(d, 'foo')
            with open(testfile, 'w') as f:
                f.write('foo')

            cmd = envelope.AttachCommand(path=testfile)
            cmd.apply(ui)
        ui.current_buffer.envelope.attach.assert_called_with(testfile)

    def test_user(self):
        """A test for an existing single path prefaced with ~/."""
        ui = utilities.make_ui()

        with tempfile.TemporaryDirectory() as d:
            # This mock replaces expanduser to replace "~/" with a path to the
            # temporary directory. This is easier and more reliable than
            # relying on changing an environment variable (like HOME), since it
            # doesn't rely on CPython implementation details.
            with mock.patch('alot.commands.os.path.expanduser',
                            lambda x: os.path.join(d, x[2:])):
                testfile = os.path.join(d, 'foo')
                with open(testfile, 'w') as f:
                    f.write('foo')

                cmd = envelope.AttachCommand(path='~/foo')
                cmd.apply(ui)
        ui.current_buffer.envelope.attach.assert_called_with(testfile)

    def test_glob(self):
        """A test using a glob."""
        ui = utilities.make_ui()

        with tempfile.TemporaryDirectory() as d:
            testfile1 = os.path.join(d, 'foo')
            testfile2 = os.path.join(d, 'far')
            for t in [testfile1, testfile2]:
                with open(t, 'w') as f:
                    f.write('foo')

            cmd = envelope.AttachCommand(path=os.path.join(d, '*'))
            cmd.apply(ui)
        ui.current_buffer.envelope.attach.assert_has_calls(
            [mock.call(testfile1), mock.call(testfile2)], any_order=True)

    def test_no_match(self):
        """A test for a file that doesn't exist."""
        ui = utilities.make_ui()

        with tempfile.TemporaryDirectory() as d:
            cmd = envelope.AttachCommand(path=os.path.join(d, 'doesnt-exist'))
            cmd.apply(ui)
        ui.notify.assert_called()


class TestTagCommands(unittest.TestCase):

    def _test(self, tagstring, action, expected):
        """Common steps for envelope.TagCommand tests

        :param tagstring: the string to pass to the TagCommand
        :type tagstring: str
        :param action: the action to pass to the TagCommand
        :type action: str
        :param expected: the expected output to assert in the test
        :type expected: list(str)
        """
        env = Envelope(tags=['one', 'two', 'three'])
        ui = utilities.make_ui()
        ui.current_buffer = mock.Mock()
        ui.current_buffer.envelope = env
        cmd = envelope.TagCommand(tags=tagstring, action=action)
        cmd.apply(ui)
        actual = env.tags
        self.assertListEqual(sorted(actual), sorted(expected))

    def test_add_new_tags(self):
        self._test(u'four', 'add', ['one', 'two', 'three', 'four'])

    def test_adding_existing_tags_has_no_effect(self):
        self._test(u'one', 'add', ['one', 'two', 'three'])

    def test_remove_existing_tags(self):
        self._test(u'one', 'remove', ['two', 'three'])

    def test_remove_non_existing_tags_has_no_effect(self):
        self._test(u'four', 'remove', ['one', 'two', 'three'])

    def test_set_tags(self):
        self._test(u'a,b,c', 'set', ['a', 'b', 'c'])

    def test_toggle_will_remove_existing_tags(self):
        self._test(u'one', 'toggle', ['two', 'three'])

    def test_toggle_will_add_new_tags(self):
        self._test(u'four', 'toggle', ['one', 'two', 'three', 'four'])

    def test_toggle_can_remove_and_add_in_one_run(self):
        self._test(u'one,four', 'toggle', ['two', 'three', 'four'])


class TestSignCommand(unittest.TestCase):

    """Tests for the SignCommand class."""

    @staticmethod
    def _make_ui_mock():
        """Create a mock for the ui and envelope and return them."""
        envelope = Envelope()
        envelope['From'] = 'foo <foo@example.com>'
        envelope.sign = mock.sentinel.default
        envelope.sign_key = mock.sentinel.default
        ui = utilities.make_ui(current_buffer=mock.Mock(envelope=envelope))
        return envelope, ui

    @mock.patch('alot.commands.envelope.crypto.get_key',
                mock.Mock(return_value=mock.sentinel.keyid))
    def test_apply_keyid_success(self):
        """If there is a valid keyid then key and to sign should be set.
        """
        env, ui = self._make_ui_mock()
        # The actual keyid doesn't matter, since it'll be mocked anyway
        cmd = envelope.SignCommand(action='sign', keyid=['a'])
        cmd.apply(ui)

        self.assertTrue(env.sign)
        self.assertEqual(env.sign_key, mock.sentinel.keyid)

    @mock.patch('alot.commands.envelope.crypto.get_key',
                mock.Mock(side_effect=GPGProblem('sentinel', 0)))
    def test_apply_keyid_gpgproblem(self):
        """If there is an invalid keyid then the signing key and to sign should
        be set to false and default.
        """
        env, ui = self._make_ui_mock()
        # The actual keyid doesn't matter, since it'll be mocked anyway
        cmd = envelope.SignCommand(action='sign', keyid=['a'])
        cmd.apply(ui)
        self.assertFalse(env.sign)
        self.assertEqual(env.sign_key, mock.sentinel.default)
        ui.notify.assert_called_once()

    @mock.patch('alot.commands.envelope.settings.account_matching_address',
                mock.Mock(side_effect=NoMatchingAccount))
    def test_apply_no_keyid_nomatchingaccount(self):
        """If there is a nokeyid and no account can be found to match the From,
        then the envelope should not be marked to sign.
        """
        env, ui = self._make_ui_mock()
        # The actual keyid doesn't matter, since it'll be mocked anyway
        cmd = envelope.SignCommand(action='sign', keyid=None)
        cmd.apply(ui)

        self.assertFalse(env.sign)
        self.assertEqual(env.sign_key, mock.sentinel.default)
        ui.notify.assert_called_once()

    def test_apply_no_keyid_no_gpg_key(self):
        """If there is a nokeyid and the account has no gpg key then the
        signing key and to sign should be set to false and default.
        """
        env, ui = self._make_ui_mock()
        env.account = mock.Mock(gpg_key=None)

        cmd = envelope.SignCommand(action='sign', keyid=None)
        cmd.apply(ui)

        self.assertFalse(env.sign)
        self.assertEqual(env.sign_key, mock.sentinel.default)
        ui.notify.assert_called_once()

    def test_apply_no_keyid_default(self):
        """If there is no keyid and the account has a gpg key, then that should
        be used.
        """
        env, ui = self._make_ui_mock()
        env.account = mock.Mock(gpg_key='sentinel')

        cmd = envelope.SignCommand(action='sign', keyid=None)
        cmd.apply(ui)

        self.assertTrue(env.sign)
        self.assertEqual(env.sign_key, 'sentinel')

    @mock.patch('alot.commands.envelope.crypto.get_key',
                mock.Mock(return_value=mock.sentinel.keyid))
    def test_apply_no_sign(self):
        """If signing with a valid keyid and valid key then set sign and
        sign_key.
        """
        env, ui = self._make_ui_mock()
        # The actual keyid doesn't matter, since it'll be mocked anyway
        cmd = envelope.SignCommand(action='sign', keyid=['a'])
        cmd.apply(ui)

        self.assertTrue(env.sign)
        self.assertEqual(env.sign_key, mock.sentinel.keyid)

    @mock.patch('alot.commands.envelope.crypto.get_key',
                mock.Mock(return_value=mock.sentinel.keyid))
    def test_apply_unsign(self):
        """Test that settingun sign sets the sign to False if all other
        conditions allow for it.
        """
        env, ui = self._make_ui_mock()
        env.sign = True
        env.sign_key = mock.sentinel
        # The actual keyid doesn't matter, since it'll be mocked anyway
        cmd = envelope.SignCommand(action='unsign', keyid=['a'])
        cmd.apply(ui)

        self.assertFalse(env.sign)
        self.assertIs(env.sign_key, None)

    @mock.patch('alot.commands.envelope.crypto.get_key',
                mock.Mock(return_value=mock.sentinel.keyid))
    def test_apply_togglesign(self):
        """Test that toggling changes the sign and sign_key as approriate if
        other condtiions allow for it
        """
        env, ui = self._make_ui_mock()
        env.sign = True
        env.sign_key = mock.sentinel.keyid

        # The actual keyid doesn't matter, since it'll be mocked anyway
        # Test that togling from true to false works
        cmd = envelope.SignCommand(action='toggle', keyid=['a'])
        cmd.apply(ui)
        self.assertFalse(env.sign)
        self.assertIs(env.sign_key, None)

        # Test that toggling back to True works
        cmd.apply(ui)
        self.assertTrue(env.sign)
        self.assertIs(env.sign_key, mock.sentinel.keyid)

    def _make_local_settings(self):
        config = textwrap.dedent("""\
            [accounts]
                [[default]]
                    realname = foo
                    address = foo@example.com
                    sendmail_command = /bin/true
            """)

        # Allow settings.reload to work by not deleting the file until the end
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(config)
        self.addCleanup(os.unlink, f.name)

        # Set the gpg_key separately to avoid validation failures
        manager = SettingsManager()
        manager.read_config(f.name)
        manager.get_accounts()[0].gpg_key = mock.sentinel.gpg_key
        return manager

    def test_apply_from_email_only(self):
        """Test that a key can be derived using a 'From' header that contains
        only an email.

        If the from header is in the form "foo@example.com" and a key exists it
        should be used.
        """
        manager = self._make_local_settings()
        env, ui = self._make_ui_mock()
        env.headers = {'From': ['foo@example.com']}

        cmd = envelope.SignCommand(action='sign')
        with mock.patch('alot.commands.envelope.settings', manager):
            cmd.apply(ui)

        self.assertTrue(env.sign)
        self.assertIs(env.sign_key, mock.sentinel.gpg_key)

    def test_apply_from_user_and_email(self):
        """This tests that a gpg key can be derived using a 'From' header that
        contains a realname-email combo.

        If the header is in the form "Foo <foo@example.com>", a key should be
        derived.

        See issue #1113
        """
        manager = self._make_local_settings()
        env, ui = self._make_ui_mock()

        cmd = envelope.SignCommand(action='sign')
        with mock.patch('alot.commands.envelope.settings', manager):
            cmd.apply(ui)

        self.assertTrue(env.sign)
        self.assertIs(env.sign_key, mock.sentinel.gpg_key)


class TestSendCommand(unittest.TestCase):

    """Tests for the SendCommand class."""

    mail = textwrap.dedent("""\
        From: foo@example.com
        To: bar@example.com
        Subject: FooBar

        Foo Bar Baz
        """)

    class MockedAccount(Account):

        def __init__(self):
            super().__init__('foo@example.com')

        async def send_mail(self, mail):
            pass

    @utilities.async_test
    async def test_account_matching_address_with_str(self):
        cmd = envelope.SendCommand(mail=self.mail)
        account = mock.Mock(wraps=self.MockedAccount())
        with mock.patch(
                'alot.commands.envelope.settings.account_matching_address',
                mock.Mock(return_value=account)) as account_matching_address:
            await cmd.apply(mock.Mock())
        account_matching_address.assert_called_once_with('foo@example.com',
                                                         return_default=True)
        # check that the apply did run through till the end.
        account.send_mail.assert_called_once_with(self.mail)

    @utilities.async_test
    async def test_account_matching_address_with_email_message(self):
        mail = email.message_from_string(self.mail)
        cmd = envelope.SendCommand(mail=mail)
        account = mock.Mock(wraps=self.MockedAccount())
        with mock.patch(
                'alot.commands.envelope.settings.account_matching_address',
                mock.Mock(return_value=account)) as account_matching_address:
            await cmd.apply(mock.Mock())
        account_matching_address.assert_called_once_with('foo@example.com',
                                                         return_default=True)
        # check that the apply did run through till the end.
        account.send_mail.assert_called_once_with(mail)
