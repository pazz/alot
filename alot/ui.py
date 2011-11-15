"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
import urwid
from twisted.internet import reactor, defer

from settings import config
from buffers import BufferlistBuffer
import commands
from commands import commandfactory
from alot.commands import CommandParseError
import widgets
from completion import CommandLineCompleter


class InputWrap(urwid.WidgetWrap):
    def __init__(self, ui, rootwidget):
        urwid.WidgetWrap.__init__(self, rootwidget)
        self.ui = ui
        self.rootwidget = rootwidget
        self.select_cancel_only = False

    def set_root(self, w):
        self._w = w

    def get_root(self):
        return self._w

    def allowed_command(self, cmd):
        if not self.select_cancel_only:
            return True
        elif isinstance(cmd, commands.globals.SendKeypressCommand):
            if cmd.key in ['select', 'cancel']:
                return True
        else:
            return False

    def keypress(self, size, key):
        self.ui.logger.debug('got key: \'%s\'' % key)
        mode = self.ui.mode
        if self.select_cancel_only:
            mode = 'global'
        cmdline = config.get_mapping(mode, key)
        if cmdline:
            try:
                cmd = commandfactory(cmdline, mode)
                if self.allowed_command(cmd):
                    self.ui.apply_command(cmd)
                    return None
            except CommandParseError, e:
                self.ui.notify(e.message, priority='error')
        self.ui.logger.debug('relaying key: %s' % key)
        return self._w.keypress(size, key)


class UI(object):
    buffers = []
    current_buffer = None

    def __init__(self, dbman, log, accountman, initialcmd, colourmode):
        self.dbman = dbman
        self.dbman.ui = self  # register ui with dbman
        self.logger = log
        self.accountman = accountman

        if not colourmode:
            colourmode = config.getint('general', 'colourmode')
        self.logger.info('setup gui in %d colours' % colourmode)
        self.mainframe = urwid.Frame(urwid.SolidFill())
        self.inputwrap = InputWrap(self, self.mainframe)
        self.mainloop = urwid.MainLoop(self.inputwrap,
                config.get_palette(),
                handle_mouse=False,
                event_loop=urwid.TwistedEventLoop(),
                unhandled_input=self.unhandeled_input)
        self.mainloop.screen.set_terminal_properties(colors=colourmode)

        self.show_statusbar = config.getboolean('general', 'show_statusbar')
        self.notificationbar = None
        self.mode = 'global'
        self.commandprompthistory = []

        self.logger.debug('fire first command')
        self.apply_command(initialcmd)
        self.mainloop.run()

    def unhandeled_input(self, key):
        self.logger.debug('unhandeled input: %s' % key)

    def keypress(self, key):
        self.inputwrap.keypress((150, 20), key)

    def show_as_root_until_keypress(self, w, key, relay_rest=True,
                                    afterwards=None):
        def oe():
            self.inputwrap.set_root(self.mainframe)
            self.inputwrap.select_cancel_only = False
            if callable(afterwards):
                self.logger.debug('called')
                afterwards()
        self.logger.debug('relay: %s' % relay_rest)
        helpwrap = widgets.CatchKeyWidgetWrap(w, key, on_catch=oe,
                                              relay_rest=relay_rest)
        self.inputwrap.set_root(helpwrap)
        self.inputwrap.select_cancel_only = not relay_rest

    def prompt(self, prefix='>', text=u'', completer=None, tab=0, history=[],
            hidechars=False):
        """prompt for text input

        :param prefix: text to print before the input field
        :type prefix: str
        :param text: initial content of the input field
        :type text: str
        :param completer: completion object to use
        :type completer: `alot.completion.Completer`
        :param tab: number of tabs to press initially
                    (to select completion results)
        :type tab: int
        :param history: history to be used for up/down keys
        :type history: list of str
        :returns: a `twisted.defer.Deferred`
        :param hidechars: hide input repeating '*' for pwd entries
        :type prefix: boolean
        """
        d = defer.Deferred()  # create return deferred
        oldroot = self.inputwrap.get_root()

        def select_or_cancel(text):
            # restore main screen
            self.inputwrap.set_root(oldroot)
            self.inputwrap.select_cancel_only = False
            d.callback(text)

        #set up widgets
        leftpart = urwid.Text(prefix, align='left')
        if hidechars:
            editpart = widgets.PasswordEdit(on_exit=select_or_cancel)
        else:
            editpart = widgets.CompleteEdit(completer, on_exit=select_or_cancel,
                                    edit_text=text, history=history)

        for i in range(tab):  # hit some tabs
            editpart.keypress((0,), 'tab')

        # build promptwidget
        both = urwid.Columns(
            [
                ('fixed', len(prefix), leftpart),
                ('weight', 1, editpart),
            ])
        both = urwid.AttrMap(both, 'prompt', 'prompt')

        # put promptwidget as overlay on main widget
        overlay = urwid.Overlay(both, oldroot,
                                ('fixed left', 0),
                                ('fixed right', 0),
                                ('fixed bottom', 1),
                                None)
        self.inputwrap.set_root(overlay)
        self.inputwrap.select_cancel_only = True
        return d  # return deferred

    def exit(self):
        reactor.stop()
        raise urwid.ExitMainLoop()

    @defer.inlineCallbacks
    def commandprompt(self, startstring):
        """prompt for a commandline and interpret/apply it upon enter

        :param startstring: initial text in edit part
        :type startstring: str
        """
        self.logger.info('open command shell')
        mode = self.current_buffer.typename
        cmdline = yield self.prompt(prefix=':', hidechars=True,
                              text=startstring,
                              completer=CommandLineCompleter(self.dbman,
                                                             self.accountman,
                                                             mode),
                              history=self.commandprompthistory,
                             )
        self.logger.debug('CMDLINE: %s' % cmdline)
        self.interpret_commandline(cmdline)

    def interpret_commandline(self, cmdline):
        """interpret and apply a commandstring

        :param cmdline: command string to apply
        :type cmdline: str
        """
        if cmdline:
            mode = self.current_buffer.typename
            self.commandprompthistory.append(cmdline)
            try:
                cmd = commandfactory(cmdline, mode)
                self.apply_command(cmd)
            except CommandParseError, e:
                self.notify(e.message, priority='error')

    def buffer_open(self, b):
        """
        register and focus new buffer
        """
        self.buffers.append(b)
        self.buffer_focus(b)

    def buffer_close(self, buf):
        buffers = self.buffers
        if buf not in buffers:
            string = 'tried to close unknown buffer: %s. \n\ni have:%s'
            self.logger.error(string % (buf, self.buffers))
        elif len(buffers) == 1:
            self.logger.info('closing the last buffer, exiting')
            cmd = commandfactory('exit')
            self.apply_command(cmd)
        else:
            if self.current_buffer == buf:
                self.logger.debug('UI: closing current buffer %s' % buf)
                index = buffers.index(buf)
                buffers.remove(buf)
                offset = config.getint('general', 'bufferclose_focus_offset')
                nextbuffer = buffers[(index + offset) % len(buffers)]
                self.buffer_focus(nextbuffer)
            else:
                string = 'closing buffer %d:%s'
                self.logger.debug(string % (buffers.index(buf), buf))
                buffers.remove(buf)
            buf.cleanup()

    def buffer_focus(self, buf):
        """
        focus given buffer. must be contained in self.buffers
        """
        if buf not in self.buffers:
            self.logger.error('tried to focus unknown buffer')
        else:
            if self.current_buffer != buf:
                self.current_buffer = buf
                self.inputwrap.set_root(self.mainframe)
            self.mode = buf.typename
            if isinstance(self.current_buffer, BufferlistBuffer):
                self.current_buffer.rebuild()
            self.update()

    def get_deep_focus(self, startfrom=None):
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
        """returns currently open buffers for a given subclass of
        `alot.buffer.Buffer`
        """
        return filter(lambda x: isinstance(x, t), self.buffers)

    def clear_notify(self, messages):
        """clears notification popups. Usually called in order
        to ged rid of messages that don't time out

        :param messages: The popups to remove. This should be exactly
                         what notify() returned
        """
        newpile = self.notificationbar.widget_list
        for l in messages:
            newpile.remove(l)
        if newpile:
            self.notificationbar = urwid.Pile(newpile)
        else:
            self.notificationbar = None
        self.update()

    def choice(self, message, choices={'y': 'yes', 'n': 'no'},
               select=None, cancel=None, msg_position='above'):
        """prompt user to make a choice

        :param message: string to display before list of choices
        :type message: unicode
        :param choices: dict of possible choices
        :type choices: keymap->choice (both str)
        :param select: choice to return if enter/return is hit.
                       Ignored if set to None.
        :type select: str
        :param cancel: choice to return if escape is hit.
                       Ignored if set to None.
        :type cancel: str
        :returns: a `twisted.defer.Deferred`
        """
        assert select in choices.values() + [None]
        assert cancel in choices.values() + [None]
        assert msg_position in ['left', 'above']

        d = defer.Deferred()  # create return deferred
        oldroot = self.inputwrap.get_root()

        def select_or_cancel(text):
            self.inputwrap.set_root(oldroot)
            self.inputwrap.select_cancel_only = False
            d.callback(text)

        #set up widgets
        msgpart = urwid.Text(message)
        choicespart = widgets.ChoiceWidget(choices, callback=select_or_cancel,
                                           select=select, cancel=cancel)

        # build widget
        if msg_position == 'left':
            both = urwid.Columns(
                [
                    ('fixed', len(message), msgpart),
                    ('weight', 1, choicespart),
                ], dividechars=1)
        else:  # above
            both = urwid.Pile([msgpart, choicespart])
        both = urwid.AttrMap(both, 'prompt', 'prompt')

        # put promptwidget as overlay on main widget
        overlay = urwid.Overlay(both, oldroot,
                                ('fixed left', 0),
                                ('fixed right', 0),
                                ('fixed bottom', 1),
                                None)
        self.inputwrap.set_root(overlay)
        self.inputwrap.select_cancel_only = True
        return d  # return deferred

    def notify(self, message, priority='normal', timeout=0, block=False):
        """notify popup

        :param message: message to print
        :type message: str
        :param priority: priority string, used to format the popup: currently,
                         'normal' and 'error' are defined. If you use 'X' here,
                         the attribute 'notify_X' is used to format the popup.
        :type priority: str
        :param timeout: seconds until message disappears. Defaults to the value
                        of 'notify_timeout' in the general config section.
                        A negative value means never time out.
        :type timeout: int
        :param block: this notification blocks until a keypress is made
        :type block: boolean
        """
        def build_line(msg, prio):
            cols = urwid.Columns([urwid.Text(msg)])
            return urwid.AttrMap(cols, 'notify_' + prio)
        msgs = [build_line(message, priority)]

        if not self.notificationbar:
            self.notificationbar = urwid.Pile(msgs)
        else:
            newpile = self.notificationbar.widget_list + msgs
            self.notificationbar = urwid.Pile(newpile)
        self.update()

        def clear(*args):
            self.clear_notify(msgs)

        if block:
            # put "cancel to continue" widget as overlay on main widget
            txt = urwid.Text('(cancel continues)')
            overlay = urwid.Overlay(txt, self.mainframe,
                                    ('fixed left', 0),
                                    ('fixed right', 0),
                                    ('fixed bottom', 0),
                                    None)
            self.show_as_root_until_keypress(overlay, 'cancel',
                                             relay_rest=False,
                                             afterwards=clear)
        else:
            if timeout >= 0:
                if timeout == 0:
                    timeout = config.getint('general', 'notify_timeout')
                self.mainloop.set_alarm_in(timeout, clear)
        return msgs[0]

    def update(self):
        """
        redraw interface
        """
        #who needs a header?
        #head = urwid.Text('notmuch gui')
        #h=urwid.AttrMap(head, 'header')
        #self.mainframe.set_header(h)

        # body
        if self.current_buffer:
            self.mainframe.set_body(self.current_buffer)
        else:
            # this happens iff update gets called during
            # initial command before a first buffer is displayed.
            # in compose, a prompt is cancelled
            self.exit()

        # footer
        lines = []
        if self.notificationbar:  # .get_text()[0] != ' ':
            lines.append(self.notificationbar)
        if self.show_statusbar:
            lines.append(self.build_statusbar())

        if lines:
            self.mainframe.set_footer(urwid.Pile(lines))
        else:
            self.mainframe.set_footer(None)

    def build_statusbar(self):
        idx = self.buffers.index(self.current_buffer)
        lefttxt = '%d: [%s] %s' % (idx, self.current_buffer.typename,
                                   self.current_buffer)
        footerleft = urwid.Text(lefttxt, align='left')
        righttxt = 'total messages: %d' % self.dbman.count_messages('*')
        pending_writes = len(self.dbman.writequeue)
        if pending_writes > 0:
            righttxt = ('|' * pending_writes) + ' ' + righttxt
        footerright = urwid.Text(righttxt, align='right')
        columns = urwid.Columns([
            footerleft,
            ('fixed', len(righttxt), footerright)])
        return urwid.AttrMap(columns, 'footer')

    def apply_command(self, cmd):
        if cmd:
            if cmd.prehook:
                self.logger.debug('calling pre-hook')
                try:
                    cmd.prehook(ui=self, dbm=self.dbman, aman=self.accountman,
                                log=self.logger, config=config)

                except:
                    self.logger.exception('prehook failed')
            self.logger.debug('apply command: %s' % cmd)
            cmd.apply(self)
            if cmd.posthook:
                self.logger.debug('calling post-hook')
                try:
                    cmd.posthook(ui=self, dbm=self.dbman, aman=self.accountman,
                                log=self.logger, config=config)
                except:
                    self.logger.exception('posthook failed')
