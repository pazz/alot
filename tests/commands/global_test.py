# encoding=utf-8
# Copyright © 2017 Dylan Baker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for global commands."""

from __future__ import absolute_import

from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks
import mock

from alot.commands import globals as g_commands


def expected_failure(func):
    func.todo = 'Expected Failure'
    return func


class Stop(Exception):
    """exception for stopping testing of giant unmanagable functions."""
    pass


class TestComposeCommand(unittest.TestCase):

    """Tests for the compose command."""

    @staticmethod
    def _make_envelope_mock():
        envelope = mock.Mock()
        envelope.headers = {'From': 'foo <foo@example.com>'}
        envelope.get = envelope.headers.get
        envelope.sign_key = None
        envelope.sign = False
        return envelope

    @staticmethod
    def _make_account_mock(sign_by_default=True, gpg_key=mock.sentinel.gpg_key):
        account = mock.Mock()
        account.sign_by_default = sign_by_default
        account.gpg_key = gpg_key
        account.signature = None
        return account

    @inlineCallbacks
    def test_apply_sign_by_default_okay(self):
        envelope = self._make_envelope_mock()
        account = self._make_account_mock()
        cmd = g_commands.ComposeCommand(envelope=envelope)

        # This whole mess is required becasue ComposeCommand.apply is waaaaay
        # too complicated, it needs to be split into more manageable segments.
        with mock.patch('alot.commands.globals.settings.get_account_by_address',
                        mock.Mock(return_value=account)):
            with mock.patch('alot.commands.globals.settings.get_accounts',
                            mock.Mock(return_value=[account])):
                with mock.patch('alot.commands.globals.settings.get_addressbooks',
                                mock.Mock(side_effect=Stop)):
                    try:
                        yield cmd.apply(mock.Mock())
                    except Stop:
                        pass

        self.assertTrue(envelope.sign)
        self.assertIs(envelope.sign_key, mock.sentinel.gpg_key)

    @expected_failure  # sign_key is set even though sign is False
    @inlineCallbacks
    def test_apply_sign_by_default_false_doesnt_set_key(self):
        envelope = self._make_envelope_mock()
        account = self._make_account_mock(sign_by_default=False)
        cmd = g_commands.ComposeCommand(envelope=envelope)

        # This whole mess is required becasue ComposeCommand.apply is waaaaay
        # too complicated, it needs to be split into more manageable segments.
        with mock.patch('alot.commands.globals.settings.get_account_by_address',
                        mock.Mock(return_value=account)):
            with mock.patch('alot.commands.globals.settings.get_accounts',
                            mock.Mock(return_value=[account])):
                with mock.patch('alot.commands.globals.settings.get_addressbooks',
                                mock.Mock(side_effect=Stop)):
                    try:
                        yield cmd.apply(mock.Mock())
                    except Stop:
                        pass

        self.assertFalse(envelope.sign)
        self.assertIs(envelope.sign_key, None)

    @expected_failure  # sign is set even though there is no sign_key
    @inlineCallbacks
    def test_apply_sign_by_default_but_no_key(self):
        envelope = self._make_envelope_mock()
        account = self._make_account_mock(gpg_key=None)
        cmd = g_commands.ComposeCommand(envelope=envelope)

        # This whole mess is required becasue ComposeCommand.apply is waaaaay
        # too complicated, it needs to be split into more manageable segments.
        with mock.patch('alot.commands.globals.settings.get_account_by_address',
                        mock.Mock(return_value=account)):
            with mock.patch('alot.commands.globals.settings.get_accounts',
                            mock.Mock(return_value=[account])):
                with mock.patch('alot.commands.globals.settings.get_addressbooks',
                                mock.Mock(side_effect=Stop)):
                    try:
                        yield cmd.apply(mock.Mock())
                    except Stop:
                        pass

        self.assertFalse(envelope.sign)
        self.assertIs(envelope.sign_key, None)
