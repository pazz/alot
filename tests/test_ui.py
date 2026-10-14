# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import asyncio
import signal
import unittest
from unittest import mock

import urwid

from alot.buffers import SearchBuffer
from alot.commands import Command
from alot.commands.globals import ExitCommand
from alot.ui import UI, periodic

from . import utilities


@mock.patch('alot.ui.settings.get', mock.Mock(return_value=': '))
@mock.patch('alot.ui.settings.get_theming_attribute', mock.Mock())
class TestOverlayInput(unittest.TestCase):

    def _ui(self):
        ui = UI.__new__(UI)
        ui.mainloop = mock.Mock(widget=urwid.SolidFill())
        ui._passall = False
        return ui

    def _answer(self, ui, fut, key):
        root = ui.mainloop.widget.bottom_w
        self.assertTrue(ui._passall)
        ui.mainloop.widget.top_w.keypress((80,), key)
        self.assertIs(ui.mainloop.widget, root)
        self.assertFalse(ui._passall)
        return fut.result()

    @utilities.async_test
    async def test_prompt(self):
        ui = self._ui()
        fut = ui.prompt('question', text='answer')
        self.assertEqual(self._answer(ui, fut, 'enter'), 'answer')

    @utilities.async_test
    async def test_choice(self):
        ui = self._ui()
        fut = ui.choice('question')
        self.assertEqual(self._answer(ui, fut, 'y'), 'yes')


class TestSignals(unittest.TestCase):

    @mock.patch('alot.ui.urwid.MainLoop', mock.MagicMock())
    @mock.patch('alot.ui.signal.signal', mock.Mock())
    @mock.patch('alot.ui.settings',
                mock.MagicMock(**{'get_hook.return_value': None}))
    @mock.patch('alot.ui.UI._load_history_from_file',
                mock.Mock(return_value=[]))
    def test_sigterm_stops_the_main_loop(self):
        loop = mock.Mock(**{'create_task.side_effect': lambda c: c.close()})
        UI(mock.Mock(), '', loop)
        loop.add_signal_handler.assert_called_once_with(signal.SIGTERM,
                                                        loop.stop)


class TestSignalDispatch(unittest.TestCase):

    def test_handler_schedules_handle_signal_on_the_loop(self):
        ui = UI.__new__(UI)
        loop = mock.Mock()
        with mock.patch('alot.ui.asyncio.get_event_loop', return_value=loop), \
                mock.patch('alot.ui.asyncio.run_coroutine_threadsafe') as run:
            ui._handle_signal(signal.SIGUSR1, None)
        coro, target = run.call_args.args
        self.assertIs(target, loop)
        self.assertEqual(coro.cr_code.co_name, 'handle_signal')
        coro.close()

    @utilities.async_test
    async def test_sigint_exits(self):
        ui = UI.__new__(UI)
        ui.apply_command = mock.AsyncMock()
        await ui.handle_signal(signal.SIGINT)
        self.assertIsInstance(ui.apply_command.await_args.args[0],
                              ExitCommand)

    @utilities.async_test
    async def test_sigusr1_refreshes_a_search_buffer(self):
        ui = UI.__new__(UI)
        ui.current_buffer = mock.Mock(spec=SearchBuffer)
        ui.update = mock.Mock()
        await ui.handle_signal(signal.SIGUSR1)
        ui.current_buffer.rebuild.assert_called_once_with()
        ui.update.assert_called_once_with()


class FailingCommand(Command):
    def apply(self, ui):
        raise RuntimeError('apply failed')


class TestErrorContainment(unittest.TestCase):
    """Exceptions must not escape alot's tasks: urwid's asyncio event loop
    would stop and re-raise them."""

    def _ui(self):
        ui = UI.__new__(UI)
        ui.mode = 'global'
        ui._error_handler = mock.Mock()
        return ui

    @utilities.async_test
    async def test_failing_command(self):
        ui = self._ui()
        with mock.patch('alot.ui.commandfactory',
                        return_value=FailingCommand()):
            await ui.apply_commandline('anything')
        ui._error_handler.assert_called_once()

    @utilities.async_test
    async def test_failing_hooks(self):
        for hook in ('prehook', 'posthook'):
            with self.subTest(hook=hook):
                ui = self._ui()
                cmd = Command()
                setattr(cmd, hook, mock.AsyncMock(side_effect=RuntimeError))
                with mock.patch('alot.ui.commandfactory', return_value=cmd):
                    await ui.apply_commandline('anything')
                ui._error_handler.assert_called_once()

    @utilities.async_test
    async def test_failing_loop_hook_is_logged_and_retried(self):
        calls = []

        def hook():
            calls.append(None)
            if len(calls) < 3:
                raise RuntimeError('hook failed')
            raise asyncio.CancelledError

        with self.assertLogs(level='ERROR') as logs, \
                self.assertRaises(asyncio.CancelledError):
            await periodic(hook, 0)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(logs.records), 2)


class TestBuildStatusbar(unittest.TestCase):

    @mock.patch('alot.ui.settings')
    def test_counts_messages_only_when_shown(self, settings):
        ui = UI.__new__(UI)
        ui.current_buffer = mock.Mock(modename='search',
                                      **{'get_info.return_value': {}})
        ui.buffers = [ui.current_buffer]
        ui.dbman = mock.Mock(writequeue=[], **{'count_messages.return_value': 7})
        ui.input_queue = []
        settings.get.return_value = ('left', 'right')
        ui.build_statusbar()
        ui.dbman.count_messages.assert_not_called()
        settings.get.return_value = ('left', '{total_messages} messages')
        ui.build_statusbar()
        ui.dbman.count_messages.assert_called_once_with('*')


class TestUpdate(unittest.TestCase):

    @mock.patch('alot.ui.settings')
    def test_applies_the_current_theme_background(self, settings):
        ui = UI.__new__(UI)
        ui.root_widget = urwid.AttrMap(urwid.Frame(urwid.SolidFill()), 'old')
        ui.current_buffer = None
        ui._notificationbar = None
        ui._show_statusbar = False
        ui.mainloop = mock.Mock()
        settings.get_theming_attribute.return_value = 'new'
        ui.update()  # e.g. after the theme command
        self.assertEqual(ui.root_widget.attr_map, {None: 'new'})
