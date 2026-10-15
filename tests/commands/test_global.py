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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for global commands."""

import os
import tempfile
import unittest
from unittest import mock

from alot.commands import globals as g_commands
from alot.commands import search as s_commands
from alot.db.errors import DatabaseROError
from alot.ui import UI

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

    def test_set_gpg_sign_by_default_okay(self):
        envelope = self._make_envelope_mock()
        envelope.account = self._make_account_mock()
        cmd = g_commands.ComposeCommand(envelope=envelope)

        cmd._set_gpg_sign(mock.Mock())

        self.assertTrue(envelope.sign)
        self.assertIs(envelope.sign_key, mock.sentinel.gpg_key)

    def test_set_gpg_sign_by_default_false_doesnt_set_key(self):
        envelope = self._make_envelope_mock()
        envelope.account = self._make_account_mock(sign_by_default=False)
        cmd = g_commands.ComposeCommand(envelope=envelope)

        cmd._set_gpg_sign(mock.Mock())

        self.assertFalse(envelope.sign)
        self.assertIs(envelope.sign_key, None)

    def test_set_gpg_sign_by_default_but_no_key(self):
        envelope = self._make_envelope_mock()
        envelope.account = self._make_account_mock(gpg_key=None)
        cmd = g_commands.ComposeCommand(envelope=envelope)

        cmd._set_gpg_sign(mock.Mock())

        self.assertFalse(envelope.sign)
        self.assertIs(envelope.sign_key, None)

    def test_get_template_decode(self):
        subject = 'This is a täßϑ subject.'
        to = 'recipient@mail.com'
        _from = 'foo.bar@mail.fr'
        body = 'Body\n地初店会継思識棋御招告外児山望掲領環。\n€mail body €nd.'
        with tempfile.NamedTemporaryFile('wb', delete=False) as f:
            txt = 'Subject: {}\nTo: {}\nFrom: {}\n{}'.format(subject, to,
                                                              _from, body)
            f.write(txt.encode('utf-8'))
        self.addCleanup(os.unlink, f.name)

        cmd = g_commands.ComposeCommand(template=f.name)
        cmd._set_envelope()
        cmd._get_template(mock.Mock())

        self.assertEqual({'To': [to],
                          'From': [_from],
                          'Subject': [subject]}, cmd.envelope.headers)
        self.assertEqual(body, cmd.envelope.body_txt)

    @mock.patch('alot.commands.globals.settings.get', return_value=True)
    @utilities.async_test
    async def test_cancel_tags_prompt(self, _):
        ui = utilities.make_ui(prompt=mock.AsyncMock(return_value=None))
        with self.assertRaises(g_commands.CommandCanceled):
            await g_commands.ComposeCommand()._set_compose_tags(ui)

    @utilities.async_test
    async def test_missing_signature_prompt(self):
        envelope = self._make_envelope_mock()
        envelope.account = self._make_account_mock()
        envelope.account.signature = '/nonexistent/signature'
        ui = utilities.make_ui(_overlay_input=mock.AsyncMock(return_value='no'))
        ui.choice = lambda *args, **kwargs: UI.choice(ui, *args, **kwargs)
        cmd = g_commands.ComposeCommand(envelope=envelope)
        with self.assertRaises(cmd.ApplyError):
            await cmd._set_signature(ui)


class TestExitCommand(unittest.TestCase):

    @utilities.async_test
    async def test_refuses_while_editor_runs(self):
        ui = utilities.make_ui(buffers=[], editors=0, db_was_locked=False)

        async def quit_from_editor(cmd, ui):
            await g_commands.ExitCommand().apply(ui)

        config = {'editor_cmd': 'vi', 'editor_spawn': False,
                  'editor_in_thread': True, 'bug_on_exit': False}
        with mock.patch('alot.commands.globals.settings.get', config.get), \
                mock.patch('alot.commands.globals.settings.get_hook',
                           return_value=None), \
                mock.patch.object(g_commands.ExternalCommand, 'apply',
                                  quit_from_editor):
            await g_commands.EditCommand('/tmp/draft').apply(ui)
        ui.exit.assert_not_called()
        ui.apply_command.assert_not_called()
        self.assertEqual(ui.editors, 0)


class TestExternalCommand(unittest.TestCase):

    @utilities.async_test
    async def test_no_spawn_no_stdin_success(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand('true', refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    async def test_no_spawn_stdin_success(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand("awk '{ exit $0 }'", stdin='0',
                                         refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    async def test_no_spawn_no_stdin_attached(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand('test -p /dev/stdin', refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_called_once_with(
                'command has exited with error code 1 -- No stderr output',
                priority='error')

    @utilities.async_test
    async def test_no_spawn_stdin_attached(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(
            "test -p /dev/stdin", stdin='0', refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    async def test_no_spawn_failure(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand('false', refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_called_once_with(
                'command has exited with error code 1 -- No stderr output',
                priority='error')

    @utilities.async_test
    async def test_shell_in_thread(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand('exit 3', shell=True, thread=True,
                                         refocus=False)
        await cmd.apply(ui)
        ui.notify.assert_called_once_with(
                'command has exited with error code 3 -- No stderr output',
                priority='error')

    @utilities.async_test
    @mock.patch(
        'alot.commands.globals.settings.get', mock.Mock(return_value=''))
    @mock.patch.dict(os.environ, {'DISPLAY': ':0'})
    async def test_spawn_no_stdin_success(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand('true', refocus=False, spawn=True)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    @mock.patch(
        'alot.commands.globals.settings.get', mock.Mock(return_value=''))
    @mock.patch.dict(os.environ, {'DISPLAY': ':0'})
    async def test_spawn_stdin_success(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand(
            "awk '{ exit $0 }'",
            stdin='0', refocus=False, spawn=True)
        await cmd.apply(ui)
        ui.notify.assert_not_called()

    @utilities.async_test
    @mock.patch(
        'alot.commands.globals.settings.get', mock.Mock(return_value=''))
    @mock.patch.dict(os.environ, {'DISPLAY': ':0'})
    async def test_spawn_failure(self):
        ui = utilities.make_ui()
        cmd = g_commands.ExternalCommand('false', refocus=False, spawn=True)
        await cmd.apply(ui)
        ui.notify.assert_called_once_with(
                'command has exited with error code 1 -- No stderr output',
                priority='error')


class TestCallCommand(unittest.TestCase):

    @utilities.async_test
    async def test_synchronous_call(self):
        ui = mock.Mock()
        cmd = g_commands.CallCommand('ui()')
        await cmd.apply(ui)
        ui.assert_called_once()

    @utilities.async_test
    async def test_async_call(self):
        async def func(obj):
            obj()

        ui = mock.Mock()
        hooks = mock.Mock()
        hooks.ui = None
        hooks.func = func

        with mock.patch('alot.commands.globals.settings.hooks', hooks):
            cmd = g_commands.CallCommand('hooks.func(ui)')
            await cmd.apply(ui)
            ui.assert_called_once()


class TestNamedQueryCommands(unittest.TestCase):

    commands = [g_commands.SaveQueryCommand('alias', ['tag:foo']),
                s_commands.SaveQueryCommand('alias', ['tag:foo']),
                g_commands.RemoveQueryCommand('alias')]

    @utilities.async_test
    async def test_flushes(self):
        for cmd in self.commands:
            with self.subTest(cmd=cmd):
                ui = utilities.make_ui(apply_command=mock.AsyncMock())
                await cmd.apply(ui)
                ui.apply_command.assert_awaited_once()

    @utilities.async_test
    async def test_read_only_index(self):
        ui = utilities.make_ui()
        ui.dbman.remove_named_query.side_effect = DatabaseROError
        await g_commands.RemoveQueryCommand('alias').apply(ui)
        ui.notify.assert_called_once_with(
            'index in read-only mode', priority='error')
