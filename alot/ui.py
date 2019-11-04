# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import logging
import os
import signal
import codecs
import contextlib
import asyncio
import traceback

import urwid

from .settings.const import settings
from .buffers import BufferlistBuffer
from .buffers import SearchBuffer
from .commands import globals
from .commands import commandfactory
from .commands import CommandCanceled
from .commands import CommandParseError
from .helper import split_commandline
from .helper import string_decode
from .helper import get_xdg_env
from .widgets.globals import CompleteEdit
from .widgets.globals import ChoiceWidget


async def periodic(callable_, period, *args, **kwargs):
    while True:
        try:
            callable_(*args, **kwargs)
        except Exception as e:
            logging.error('error in loop hook %s', str(e))
        await asyncio.sleep(period)


class UI:
    """
    This class integrates all components of alot and offers
    methods for user interaction like :meth:`prompt`, :meth:`notify` etc.
    It handles the urwid widget tree and mainloop (we use asyncio) and is
    responsible for opening, closing and focussing buffers.
    """

    def __init__(self, dbman, initialcmdline):
        """
        :param dbman: :class:`~alot.db.DBManager`
        :param initialcmdline: commandline applied after setting up interface
        :type initialcmdline: str
        :param colourmode: determines which theme to chose
        :type colourmode: int in [1,16,256]
        """
        self.dbman = dbman
        """Database Manager (:class:`~alot.db.manager.DBManager`)"""
        self.buffers = []
        """list of active buffers"""
        self.current_buffer = None
        """points to currently active :class:`~alot.buffers.Buffer`"""
        self.db_was_locked = False
        """flag used to prevent multiple 'index locked' notifications"""
        self.mode = 'global'
        """interface mode identifier - type of current buffer"""
        self.commandprompthistory = []
        """history of the command line prompt"""
        self.senderhistory = []
        """history of the sender prompt"""
        self.recipienthistory = []
        """history of the recipients prompt"""
        self.input_queue = []
        """stores partial keyboard input"""
        self.last_commandline = None
        """saves the last executed commandline"""

        # define empty notification pile
        self._notificationbar = None
        # should we show a status bar?
        self._show_statusbar = settings.get('show_statusbar')
        # pass keypresses to the root widget and never interpret bindings
        self._passall = False
        # indicates "input lock": only focus move commands are interpreted
        self._locked = False
        self._unlock_callback = None  # will be called after input lock ended
        self._unlock_key = None  # key that ends input lock

        # alarm handle for callback that clears input queue (to cancel alarm)
        self._alarm = None

        # force urwid to pass key events as unicode, independent of LANG
        urwid.set_encoding('utf-8')

        # create root widget
        global_att = settings.get_theming_attribute('global', 'body')
        mainframe = urwid.Frame(urwid.SolidFill())
        self.root_widget = urwid.AttrMap(mainframe, global_att)

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGUSR1, self.handle_signal)

        # load histories
        self._cache = os.path.join(
            get_xdg_env('XDG_CACHE_HOME', os.path.expanduser('~/.cache')),
            'alot', 'history')
        self._cmd_hist_file = os.path.join(self._cache, 'commands')
        self._sender_hist_file = os.path.join(self._cache, 'senders')
        self._recipients_hist_file = os.path.join(self._cache, 'recipients')
        size = settings.get('history_size')
        self.commandprompthistory = self._load_history_from_file(
            self._cmd_hist_file, size=size)
        self.senderhistory = self._load_history_from_file(
            self._sender_hist_file, size=size)
        self.recipienthistory = self._load_history_from_file(
            self._recipients_hist_file, size=size)

        # set up main loop
        self.mainloop = urwid.MainLoop(
            self.root_widget,
            handle_mouse=settings.get('handle_mouse'),
            event_loop=urwid.TwistedEventLoop(),
            unhandled_input=self._unhandled_input,
            input_filter=self._input_filter)

        loop = asyncio.get_event_loop()
        # Create a task for the periodic hook
        loop_hook = settings.get_hook('loop_hook')
        if loop_hook:
            # In Python 3.7 a nice aliase `asyncio.create_task` was added
            loop.create_task(
                periodic(
                    loop_hook, settings.get('periodic_hook_frequency'),
                    ui=self))

        # set up colours
        colourmode = int(settings.get('colourmode'))
        logging.info('setup gui in %d colours', colourmode)
        self.mainloop.screen.set_terminal_properties(colors=colourmode)

        logging.debug('fire first command')
        loop.create_task(self.apply_commandline(initialcmdline))

        # start urwids mainloop
        self.mainloop.run()

    def _error_handler(self, exception):
        if isinstance(exception, CommandParseError):
            self.notify(str(exception), priority='error')
        elif isinstance(exception, CommandCanceled):
            self.notify("operation cancelled", priority='error')
        else:
            logging.error(traceback.format_exc())
            msg = "{}\n(check the log for details)".format(exception)
            self.notify(msg, priority='error')

    def _input_filter(self, keys, raw):
        """
        handles keypresses.
        This function gets triggered directly by class:`urwid.MainLoop`
        upon user input and is supposed to pass on its `keys` parameter
        to let the root widget handle keys. We intercept the input here
        to trigger custom commands as defined in our keybindings.
        """
        logging.debug("Got key (%s, %s)", keys, raw)
        # work around: escape triggers this twice, with keys = raw = []
        # the first time..
        if not keys:
            return
        # let widgets handle input if key is virtual window resize keypress
        # or we are in "passall" mode
        elif 'window resize' in keys or self._passall:
            return keys
        # end "lockdown" mode if the right key was pressed
        elif self._locked and keys[0] == self._unlock_key:
            self._locked = False
            self.mainloop.widget = self.root_widget
            if callable(self._unlock_callback):
                self._unlock_callback()
        # otherwise interpret keybinding
        else:
            def clear(*_):
                """Callback that resets the input queue."""
                if self._alarm is not None:
                    self.mainloop.remove_alarm(self._alarm)
                self.input_queue = []

            async def _apply_fire(cmdline):
                try:
                    await self.apply_commandline(cmdline)
                except CommandParseError as e:
                    self.notify(str(e), priority='error')

            def fire(_, cmdline):
                clear()
                logging.debug("cmdline: '%s'", cmdline)
                if not self._locked:
                    loop = asyncio.get_event_loop()
                    loop.create_task(_apply_fire(cmdline))
                # move keys are always passed
                elif cmdline in ['move up', 'move down', 'move page up',
                                 'move page down']:
                    return [cmdline[5:]]

            key = keys[0]
            if key and 'mouse' in key[0]:
                key = key[0] + ' %i' % key[1]
            self.input_queue.append(key)
            keyseq = ' '.join(self.input_queue)
            candidates = settings.get_mapped_input_keysequences(self.mode,
                                                                prefix=keyseq)
            if keyseq in candidates:
                # case: current input queue is a mapped keysequence
                # get binding and interpret it if non-null
                cmdline = settings.get_keybinding(self.mode, keyseq)
                if cmdline:
                    if len(candidates) > 1:
                        timeout = float(settings.get('input_timeout'))
                        if self._alarm is not None:
                            self.mainloop.remove_alarm(self._alarm)
                        self._alarm = self.mainloop.set_alarm_in(
                            timeout, fire, cmdline)
                    else:
                        return fire(self.mainloop, cmdline)

            elif not candidates:
                # case: no sequence with prefix keyseq is mapped
                # just clear the input queue
                clear()
            else:
                # case: some sequences with proper prefix keyseq is mapped
                timeout = float(settings.get('input_timeout'))
                if self._alarm is not None:
                    self.mainloop.remove_alarm(self._alarm)
                self._alarm = self.mainloop.set_alarm_in(timeout, clear)
            # update statusbar
            self.update()

    async def apply_commandline(self, cmdline):
        """
        interprets a command line string

        i.e., splits it into separate command strings,
        instanciates :class:`Commands <alot.commands.Command>`
        accordingly and applies then in sequence.

        :param cmdline: command line to interpret
        :type cmdline: str
        """
        # remove initial spaces
        cmdline = cmdline.lstrip()

        # we pass Commands one by one to `self.apply_command`.
        # To properly call them in sequence, even if they trigger asyncronous
        # code (return Deferreds), these applications happen in individual
        # callback functions which are then used as callback chain to some
        # trivial Deferred that immediately calls its first callback. This way,
        # one callback may return a Deferred and thus postpone the application
        # of the next callback (and thus Command-application)

        def apply_this_command(cmdstring):
            logging.debug('%s command string: "%s"', self.mode, str(cmdstring))
            # translate cmdstring into :class:`Command`
            cmd = commandfactory(cmdstring, self.mode)
            # store cmdline for use with 'repeat' command
            if cmd.repeatable:
                self.last_commandline = cmdline
            return self.apply_command(cmd)

        try:
            for c in split_commandline(cmdline):
                await apply_this_command(c)
        except Exception as e:
            self._error_handler(e)

    @staticmethod
    def _unhandled_input(key):
        """
        Called by :class:`urwid.MainLoop` if a keypress was passed to the root
        widget by `self._input_filter` but is not handled in any widget. We
        keep it for debugging purposes.
        """
        logging.debug('unhandled input: %s', key)

    def show_as_root_until_keypress(self, w, key, afterwards=None):
        """
        Replaces root widget by given :class:`urwid.Widget` and makes the UI
        ignore all further commands apart from cursor movement.
        If later on `key` is pressed, the old root widget is reset, callable
        `afterwards` is called and normal behaviour is resumed.
        """
        self.mainloop.widget = w
        self._unlock_key = key
        self._unlock_callback = afterwards
        self._locked = True

    def prompt(self, prefix, text='', completer=None, tab=0, history=None):
        """
        prompt for text input.
        This returns a :class:`asyncio.Future`, which will have a string value

        :param prefix: text to print before the input field
        :type prefix: str
        :param text: initial content of the input field
        :type text: str
        :param completer: completion object to use
        :type completer: :meth:`alot.completion.Completer`
        :param tab: number of tabs to press initially
                    (to select completion results)
        :type tab: int
        :param history: history to be used for up/down keys
        :type history: list of str
        :rtype: asyncio.Future
        """
        history = history or []

        fut = asyncio.get_event_loop().create_future()
        oldroot = self.mainloop.widget

        def select_or_cancel(text):
            """Restore the main screen and invoce the callback (delayed return)
            with the given text."""
            self.mainloop.widget = oldroot
            self._passall = False
            fut.set_result(text)

        def cerror(e):
            logging.error(e)
            self.notify('completion error: %s' % str(e),
                        priority='error')
            self.update()

        prefix = prefix + settings.get('prompt_suffix')

        # set up widgets
        leftpart = urwid.Text(prefix, align='left')
        editpart = CompleteEdit(completer, on_exit=select_or_cancel,
                                edit_text=text, history=history,
                                on_error=cerror)

        for _ in range(tab):  # hit some tabs
            editpart.keypress((0,), 'tab')

        # build promptwidget
        both = urwid.Columns(
            [
                ('fixed', len(prefix), leftpart),
                ('weight', 1, editpart),
            ])
        att = settings.get_theming_attribute('global', 'prompt')
        both = urwid.AttrMap(both, att)

        # put promptwidget as overlay on main widget
        overlay = urwid.Overlay(both, oldroot,
                                ('fixed left', 0),
                                ('fixed right', 0),
                                ('fixed bottom', 1),
                                None)
        self.mainloop.widget = overlay
        self._passall = True
        return fut

    @staticmethod
    def exit():
        """
        shuts down user interface without cleaning up.
        Use a :class:`alot.commands.globals.ExitCommand` for a clean shutdown.
        """
        try:
            loop = asyncio.get_event_loop()
            loop.stop()
        except Exception as e:
            logging.error('Could not stop loop: %s\nShutting down anyway..',
                          str(e))

    @contextlib.contextmanager
    def paused(self):
        """
        context manager that pauses the UI to allow running external commands.

        If an exception occurs, the UI will be started before the exception is
        re-raised.
        """
        self.mainloop.stop()
        try:
            yield
        finally:
            self.mainloop.start()

            # make sure urwid renders its canvas at the correct size
            self.mainloop.screen_size = None
            self.mainloop.draw_screen()

    def buffer_open(self, buf):
        """register and focus new :class:`~alot.buffers.Buffer`."""

        # call pre_buffer_open hook
        prehook = settings.get_hook('pre_buffer_open')
        if prehook is not None:
            prehook(ui=self, dbm=self.dbman, buf=buf)

        if self.current_buffer is not None:
            offset = settings.get('bufferclose_focus_offset') * -1
            currentindex = self.buffers.index(self.current_buffer)
            self.buffers.insert(currentindex + offset, buf)
        else:
            self.buffers.append(buf)
        self.buffer_focus(buf)

        # call post_buffer_open hook
        posthook = settings.get_hook('post_buffer_open')
        if posthook is not None:
            posthook(ui=self, dbm=self.dbman, buf=buf)

    def buffer_close(self, buf, redraw=True):
        """
        closes given :class:`~alot.buffers.Buffer`.

        This it removes it from the bufferlist and calls its cleanup() method.
        """

        # call pre_buffer_close hook
        prehook = settings.get_hook('pre_buffer_close')
        if prehook is not None:
            prehook(ui=self, dbm=self.dbman, buf=buf)

        buffers = self.buffers
        success = False
        if buf not in buffers:
            logging.error('tried to close unknown buffer: %s. \n\ni have:%s',
                          buf, self.buffers)
        elif self.current_buffer == buf:
            logging.info('closing current buffer %s', buf)
            index = buffers.index(buf)
            buffers.remove(buf)
            offset = settings.get('bufferclose_focus_offset')
            nextbuffer = buffers[(index + offset) % len(buffers)]
            self.buffer_focus(nextbuffer, redraw)
            buf.cleanup()
            success = True
        else:
            buffers.remove(buf)
            buf.cleanup()
            success = True

        # call post_buffer_closed hook
        posthook = settings.get_hook('post_buffer_closed')
        if posthook is not None:
            posthook(ui=self, dbm=self.dbman, buf=buf, success=success)

    def buffer_focus(self, buf, redraw=True):
        """focus given :class:`~alot.buffers.Buffer`."""

        # call pre_buffer_focus hook
        prehook = settings.get_hook('pre_buffer_focus')
        if prehook is not None:
            prehook(ui=self, dbm=self.dbman, buf=buf)

        success = False
        if buf not in self.buffers:
            logging.error('tried to focus unknown buffer')
        else:
            if self.current_buffer != buf:
                self.current_buffer = buf
            self.mode = buf.modename
            if isinstance(self.current_buffer, BufferlistBuffer):
                self.current_buffer.rebuild()
            self.update()
            success = True

        # call post_buffer_focus hook
        posthook = settings.get_hook('post_buffer_focus')
        if posthook is not None:
            posthook(ui=self, dbm=self.dbman, buf=buf, success=success)

    def get_deep_focus(self, startfrom=None):
        """return the bottom most focussed widget of the widget tree"""
        if not startfrom:
            startfrom = self.current_buffer
        if 'get_focus' in dir(startfrom):
            focus = startfrom.get_focus()
            if isinstance(focus, tuple):
                focus = focus[0]
            if isinstance(focus, urwid.Widget):
                return self.get_deep_focus(startfrom=focus)
        return startfrom

    def get_buffers_of_type(self, t):
        """
        returns currently open buffers for a given subclass of
        :class:`~alot.buffers.Buffer`.

        :param t: Buffer class
        :type t: alot.buffers.Buffer
        :rtype: list
        """
        return [x for x in self.buffers if isinstance(x, t)]

    def clear_notify(self, messages):
        """
        Clears notification popups. Call this to ged rid of messages that don't
        time out.

        :param messages: The popups to remove. This should be exactly
                         what :meth:`notify` returned when creating the popup
        """
        newpile = self._notificationbar.widget_list
        for l in messages:
            if l in newpile:
                newpile.remove(l)
        if newpile:
            self._notificationbar = urwid.Pile(newpile)
        else:
            self._notificationbar = None
        self.update()

    def choice(self, message, choices=None, select=None, cancel=None,
               msg_position='above', choices_to_return=None):
        """
        prompt user to make a choice.

        :param message: string to display before list of choices
        :type message: unicode
        :param choices: dict of possible choices
        :type choices: dict: keymap->choice (both str)
        :param choices_to_return: dict of possible choices to return for the
                                  choices of the choices of paramter
        :type choices: dict: keymap->choice key is  str and value is any obj)
        :param select: choice to return if enter/return is hit. Ignored if set
                       to `None`.
        :type select: str
        :param cancel: choice to return if escape is hit. Ignored if set to
                       `None`.
        :type cancel: str
        :param msg_position: determines if `message` is above or left of the
                             prompt. Must be `above` or `left`.
        :type msg_position: str
        :rtype: asyncio.Future
        """
        choices = choices or {'y': 'yes', 'n': 'no'}
        assert select is None or select in choices.values()
        assert cancel is None or cancel in choices.values()
        assert msg_position in ['left', 'above']

        fut = asyncio.get_event_loop().create_future()  # Create a returned future
        oldroot = self.mainloop.widget

        def select_or_cancel(text):
            """Restore the main screen and invoce the callback (delayed return)
            with the given text."""
            self.mainloop.widget = oldroot
            self._passall = False
            fut.set_result(text)

        # set up widgets
        msgpart = urwid.Text(message)
        choicespart = ChoiceWidget(choices,
                                   choices_to_return=choices_to_return,
                                   callback=select_or_cancel, select=select,
                                   cancel=cancel)

        # build widget
        if msg_position == 'left':
            both = urwid.Columns(
                [
                    ('fixed', len(message), msgpart),
                    ('weight', 1, choicespart),
                ], dividechars=1)
        else:  # above
            both = urwid.Pile([msgpart, choicespart])
        att = settings.get_theming_attribute('global', 'prompt')
        both = urwid.AttrMap(both, att, att)

        # put promptwidget as overlay on main widget
        overlay = urwid.Overlay(both, oldroot,
                                ('fixed left', 0),
                                ('fixed right', 0),
                                ('fixed bottom', 1),
                                None)
        self.mainloop.widget = overlay
        self._passall = True
        return fut

    def notify(self, message, priority='normal', timeout=0, block=False):
        """
        opens notification popup.

        :param message: message to print
        :type message: str
        :param priority: priority string, used to format the popup: currently,
                         'normal' and 'error' are defined. If you use 'X' here,
                         the attribute 'global_notify_X' is used to format the
                         popup.
        :type priority: str
        :param timeout: seconds until message disappears. Defaults to the value
                        of 'notify_timeout' in the general config section.
                        A negative value means never time out.
        :type timeout: int
        :param block: this notification blocks until a keypress is made
        :type block: bool
        :returns: an urwid widget (this notification) that can be handed to
                  :meth:`clear_notify` for removal
        """
        def build_line(msg, prio):
            cols = urwid.Columns([urwid.Text(msg)])
            att = settings.get_theming_attribute('global', 'notify_' + prio)
            return urwid.AttrMap(cols, att)
        msgs = [build_line(message, priority)]

        if not self._notificationbar:
            self._notificationbar = urwid.Pile(msgs)
        else:
            newpile = self._notificationbar.widget_list + msgs
            self._notificationbar = urwid.Pile(newpile)
        self.update()

        def clear(*_):
            self.clear_notify(msgs)

        if block:
            # put "cancel to continue" widget as overlay on main widget
            txt = build_line('(escape continues)', priority)
            overlay = urwid.Overlay(txt, self.root_widget,
                                    ('fixed left', 0),
                                    ('fixed right', 0),
                                    ('fixed bottom', 0),
                                    None)
            self.show_as_root_until_keypress(overlay, 'esc',
                                             afterwards=clear)
        else:
            if timeout >= 0:
                if timeout == 0:
                    timeout = settings.get('notify_timeout')
                self.mainloop.set_alarm_in(timeout, clear)
        return msgs[0]

    def update(self, redraw=True):
        """redraw interface"""
        # get the main urwid.Frame widget
        mainframe = self.root_widget.original_widget

        # body
        if self.current_buffer:
            mainframe.set_body(self.current_buffer)

        # footer
        lines = []
        if self._notificationbar:  # .get_text()[0] != ' ':
            lines.append(self._notificationbar)
        if self._show_statusbar:
            lines.append(self.build_statusbar())

        if lines:
            mainframe.set_footer(urwid.Pile(lines))
        else:
            mainframe.set_footer(None)
        # force a screen redraw
        if self.mainloop.screen.started and redraw:
            self.mainloop.draw_screen()

    def build_statusbar(self):
        """construct and return statusbar widget"""
        info = {}
        cb = self.current_buffer
        btype = None

        if cb is not None:
            info = cb.get_info()
            btype = cb.modename
            info['buffer_no'] = self.buffers.index(cb)
            info['buffer_type'] = btype
        info['total_messages'] = self.dbman.count_messages('*')
        info['pending_writes'] = len(self.dbman.writequeue)
        info['input_queue'] = ' '.join(self.input_queue)

        lefttxt = righttxt = ''
        if cb is not None:
            lefttxt, righttxt = settings.get(btype + '_statusbar', ('', ''))
            lefttxt = string_decode(lefttxt, 'UTF-8')
            lefttxt = lefttxt.format(**info)
            righttxt = string_decode(righttxt, 'UTF-8')
            righttxt = righttxt.format(**info)

        footerleft = urwid.Text(lefttxt, align='left')
        pending_writes = len(self.dbman.writequeue)
        if pending_writes > 0:
            righttxt = ('|' * pending_writes) + ' ' + righttxt
        footerright = urwid.Text(righttxt, align='right')
        columns = urwid.Columns([
            footerleft,
            ('pack', footerright)])
        footer_att = settings.get_theming_attribute('global', 'footer')
        return urwid.AttrMap(columns, footer_att)

    async def apply_command(self, cmd):
        """
        applies a command

        This calls the pre and post hooks attached to the command,
        as well as :meth:`cmd.apply`.

        :param cmd: an applicable command
        :type cmd: :class:`~alot.commands.Command`
        """
        # FIXME: What are we guarding for here? We don't mention that None is
        # allowed as a value fo cmd.
        if cmd:
            if cmd.prehook:
                await cmd.prehook(ui=self, dbm=self.dbman, cmd=cmd)
            try:
                if asyncio.iscoroutinefunction(cmd.apply):
                    await cmd.apply(self)
                else:
                    cmd.apply(self)
            except Exception as e:
                self._error_handler(e)
            else:
                if cmd.posthook:
                    logging.info('calling post-hook')
                    await cmd.posthook(ui=self, dbm=self.dbman, cmd=cmd)

    def handle_signal(self, signum, frame):
        """
        handles UNIX signals

        This function currently just handles SIGUSR1. It could be extended to
        handle more

        :param signum: The signal number (see man 7 signal)
        :param frame: The execution frame
            (https://docs.python.org/2/reference/datamodel.html#frame-objects)
        """
        # it is a SIGINT ?
        if signum == signal.SIGINT:
            logging.info('shut down cleanly')
            asyncio.ensure_future(self.apply_command(globals.ExitCommand()))
        elif signum == signal.SIGUSR1:
            if isinstance(self.current_buffer, SearchBuffer):
                self.current_buffer.rebuild()
                self.update()

    def cleanup(self):
        """Do the final clean up before shutting down."""
        size = settings.get('history_size')
        self._save_history_to_file(self.commandprompthistory,
                                   self._cmd_hist_file, size=size)
        self._save_history_to_file(self.senderhistory, self._sender_hist_file,
                                   size=size)
        self._save_history_to_file(self.recipienthistory,
                                   self._recipients_hist_file, size=size)

    @staticmethod
    def _load_history_from_file(path, size=-1):
        """Load a history list from a file and split it into lines.

        :param path: the path to the file that should be loaded
        :type path: str
        :param size: the number of lines to load (0 means no lines, < 0 means
            all lines)
        :type size: int
        :returns: a list of history items (the lines of the file)
        :rtype: list(str)
        """
        if size == 0:
            return []
        if os.path.exists(path):
            with codecs.open(path, 'r', encoding='utf-8') as histfile:
                lines = [line.rstrip('\n') for line in histfile]
            if size > 0:
                lines = lines[-size:]
            return lines
        else:
            return []

    @staticmethod
    def _save_history_to_file(history, path, size=-1):
        """Save a history list to a file for later loading (possibly in another
        session).

        :param history: the history list to save
        :type history: list(str)
        :param path: the path to the file where to save the history
        :param size: the number of lines to save (0 means no lines, < 0 means
            all lines)
        :type size: int
        :type path: str
        :returns: None
        """
        if size == 0:
            return
        if size > 0:
            history = history[-size:]
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        # Write linewise to avoid building a large string in menory.
        with codecs.open(path, 'w', encoding='utf-8') as histfile:
            for line in history:
                histfile.write(line)
                histfile.write('\n')
