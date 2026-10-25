# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import asyncio
import os
import signal
import tempfile
import unittest
import warnings
from unittest import mock

import urwid

from alot.buffers import SearchBuffer
from alot.commands import Command, CommandCanceled
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
    @mock.patch('alot.ui.settings',
                mock.MagicMock(**{'get_hook.return_value': None}))
    @mock.patch('alot.ui.UI._load_history_from_file',
                mock.Mock(return_value=[]))
    @mock.patch('alot.ui.UI.cleanup', mock.Mock())
    def test_sigterm_and_sighup_stop_the_main_loop(self):
        loop = mock.Mock(**{'create_task.side_effect': lambda c: c.close()})
        with mock.patch('alot.ui.signal.signal') as install, \
                mock.patch('alot.ui.signal.getsignal'):  # not SIG_IGN
            ui = UI(mock.Mock(), '', loop)
        handlers = {args[0]: args[1] for args, _ in install.call_args_list}
        self.assertEqual(handlers[signal.SIGTERM], ui._terminate)
        self.assertEqual(handlers[signal.SIGHUP], ui._terminate)
        ui._terminate(signal.SIGTERM, None)
        loop.call_soon_threadsafe.assert_called_once_with(loop.stop)


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
    async def test_cancelled_command_is_not_an_error(self):
        ui = UI.__new__(UI)
        ui.mode = 'global'
        ui.dbman = None
        ui.notify = mock.Mock()
        cmd = Command()
        cmd.prehook = mock.AsyncMock(side_effect=CommandCanceled)
        with mock.patch('alot.ui.commandfactory', return_value=cmd):
            await ui.apply_commandline('anything')
        ui.notify.assert_called_once_with('operation cancelled')

    @utilities.async_test
    async def test_plain_function_hooks(self):
        ui = self._ui()
        ui.dbman = mock.Mock()
        cmd = Command()
        cmd.prehook = mock.Mock(return_value=None)
        cmd.posthook = mock.Mock(return_value=None)
        with mock.patch('alot.ui.commandfactory', return_value=cmd):
            await ui.apply_commandline('anything')
        ui._error_handler.assert_not_called()
        cmd.posthook.assert_called_once()

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


class TestHistoryFiles(unittest.TestCase):

    def test_round_trip_without_deprecated_codecs_open(self):
        with tempfile.TemporaryDirectory() as d, warnings.catch_warnings():
            warnings.simplefilter('error', DeprecationWarning)
            path = os.path.join(d, 'sub', 'history')
            UI._save_history_to_file(['tag inbox', 'search ä'], path)
            self.assertEqual(UI._load_history_from_file(path),
                             ['tag inbox', 'search ä'])


class TestBufferHooks(unittest.TestCase):

    def _close_with_hooks(self, hooks):
        ui = UI.__new__(UI)
        ui.dbman = mock.Mock()
        buf = mock.Mock()
        ui.current_buffer = mock.Mock()
        ui.buffers = [buf, ui.current_buffer]
        with mock.patch('alot.ui.settings.get_hook', hooks.get):
            ui.buffer_close(buf)
        return buf

    def test_post_buffer_close_is_called_as_documented(self):
        hook = mock.Mock()
        buf = self._close_with_hooks({'post_buffer_close': hook})
        hook.assert_called_once_with(ui=mock.ANY, dbm=mock.ANY, buf=buf,
                                     success=True)


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


class TestNotify(unittest.TestCase):

    @mock.patch('alot.ui.settings')
    def test_clear_notify_keeps_the_other_messages(self, _):
        ui = UI.__new__(UI)
        ui._notificationbar = None
        ui.update = mock.Mock()
        first = ui.notify('first', timeout=-1)
        second = ui.notify('second', timeout=-1)
        ui.clear_notify([first])
        self.assertEqual([w for w, _ in ui._notificationbar.contents],
                         [second])


class TestGetDeepFocus(unittest.TestCase):

    def test_follows_the_focus_into_containers(self):
        leaf = urwid.Edit()
        line = urwid.Columns([urwid.Text('>'), urwid.Pile([leaf])])
        line.focus_position = 1
        ui = UI.__new__(UI)
        ui.current_buffer = mock.Mock(**{'get_focus.return_value': (line, 0)})
        self.assertIs(ui.get_deep_focus(), leaf)
