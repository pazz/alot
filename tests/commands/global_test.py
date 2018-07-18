# encoding=utf-8
# Copyright © 2017-2018 Dylan Baker
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

import os
import tempfile
import unittest

import mock

from alot.commands import globals as g_commands

from .. import utilities


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
    def _make_account_mock(
            sign_by_default=True, gpg_key=mock.sentinel.gpg_key):
        account = mock.Mock()
        account.sign_by_default = sign_by_default
        account.gpg_key = gpg_key
        account.signature = None
        return account

    @utilities.async_test
    async def test_apply_sign_by_default_okay(self):
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
                        await cmd.apply(mock.Mock())
                    except Stop:
                        pass

        self.assertTrue(envelope.sign)
        self.assertIs(envelope.sign_key, mock.sentinel.gpg_key)

    @utilities.async_test
    async def test_apply_sign_by_default_false_doesnt_set_key(self):
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
                        await cmd.apply(mock.Mock())
                    except Stop:
                        pass

        self.assertFalse(envelope.sign)
        self.assertIs(envelope.sign_key, None)

    @utilities.async_test
    async def test_apply_sign_by_default_but_no_key(self):
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
                        await cmd.apply(mock.Mock())
                    except Stop:
                        pass

        self.assertFalse(envelope.sign)
        self.assertIs(envelope.sign_key, None)

    @utilities.async_test
    async def test_decode_template_on_loading(self):
        subject = u'This is a täßϑ subject.'
        to = u'recipient@mail.com'
        _from = u'foo.bar@mail.fr'
        body = u'Body\n地初店会継思識棋御招告外児山望掲領環。\n€mail body €nd.'
        with tempfile.NamedTemporaryFile('wb', delete=False) as f:
            txt = u'Subject: {}\nTo: {}\nFrom: {}\n{}'.format(subject, to,
                                                              _from, body)
            f.write(txt.encode('utf-8'))
        self.addCleanup(os.unlink, f.name)

        cmd = g_commands.ComposeCommand(template=f.name)

        # Crutch to exit the giant `apply` method early.
        with mock.patch(
                'alot.commands.globals.settings.get_account_by_address',
                mock.Mock(side_effect=Stop)):
            try:
                await cmd.apply(mock.Mock())
            except Stop:
                pass

        self.assertEqual({'To': [to],
                          'From': [_from],
                          'Subject': [subject]}, cmd.envelope.headers)
        self.assertEqual(body, cmd.envelope.body)

    @utilities.async_test
    async def test_single_account_no_from(self):
        # issue #1277
        envelope = self._make_envelope_mock()
        del envelope.headers['From']
        account = self._make_account_mock()
        account.realname = "foo"
        account.address = 1  # maybe this should be a real Address?
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
                        await cmd.apply(mock.Mock())
                    except Stop:
                        pass



class TestExternalCommand(unittest.TestCase):

    @utilities.async_test
    async def test_no_spawn_no_stdin_success(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(u'true', refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    async def test_no_spawn_stdin_success(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(u"awk '{ exit $0 }'", stdin=u'0',
                                         refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    async def test_no_spawn_no_stdin_attached(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(u'test -t 0', refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    async def test_no_spawn_stdin_attached(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(
            u"test -t 0", stdin=u'0', refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_called_once_with('', priority='error')

    @utilities.async_test
    async def test_no_spawn_failure(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(u'false', refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_called_once_with('', priority='error')

    @utilities.async_test
    @mock.patch(
        'alot.commands.globals.settings.get', mock.Mock(return_value=''))
    @mock.patch.dict(os.environ, {'DISPLAY': ':0'})
    async def test_spawn_no_stdin_success(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(u'true', refocus=False, spawn=True)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    @mock.patch(
        'alot.commands.globals.settings.get', mock.Mock(return_value=''))
    @mock.patch.dict(os.environ, {'DISPLAY': ':0'})
    async def test_spawn_stdin_success(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(
            u"awk '{ exit $0 }'",
            stdin=u'0', refocus=False, spawn=True)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    @mock.patch(
        'alot.commands.globals.settings.get', mock.Mock(return_value=''))
    @mock.patch.dict(os.environ, {'DISPLAY': ':0'})
    async def test_spawn_failure(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(u'false', refocus=False, spawn=True)
        await cmd.apply(ui)
        ui.notify.assert_called_once_with('', priority='error')
