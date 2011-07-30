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
import os
from urwid.command_map import command_map

from settings import config
from buffer import BufferlistBuffer
from command import commandfactory
from command import interpret_commandline
from widgets import CompleteEdit
from completion import CommandLineCompleter


class UI:
    buffers = []
    current_buffer = None

    def __init__(self, dbman, log, accountman, initialquery, colourmode):
        self.dbman = dbman
        self.dbman.ui = self  # register ui with dbman
        self.logger = log
        self.accountman = accountman

        if not colourmode:
            colourmode = config.getint('general', 'colourmode')
        self.logger.info('setup gui in %d colours' % colourmode)
        self.mainframe = urwid.Frame(urwid.SolidFill(' '))
        self.mainloop = urwid.MainLoop(self.mainframe,
                config.get_palette(),
                handle_mouse=False,
                unhandled_input=self.keypress)
        self.mainloop.screen.set_terminal_properties(colors=colourmode)

        self.show_statusbar = config.getboolean('general', 'show_statusbar')
        self.show_notificationbar = config.getboolean('general',
                                                      'show_notificationbar')
        self.notificationbar = urwid.Text(' ')
        self.mode = ''

        self.logger.debug('setup bindings')
        cmd = commandfactory('search', query=initialquery)
        self.apply_command(cmd)
        self.mainloop.run()

    def shutdown(self):
        """
        close the ui. this is _not_ the main shutdown procedure:
        there is a shutdown command that will eventually call this.
        """
        raise urwid.ExitMainLoop()

    def prompt(self, prefix='>', text=u'', tab=0, completer=None):
        self.logger.info('open prompt')
        leftpart = urwid.Text(prefix, align='left')
        if completer:
            editpart = CompleteEdit(completer, edit_text=text)
            for i in range(tab):
                editpart.keypress((0,), 'tab')
        else:
            editpart = urwid.Edit(edit_text=text)
        both = urwid.Columns(
            [
                ('fixed', len(prefix), leftpart),
                ('weight', 1, editpart),
            ])
        prompt_widget = urwid.AttrMap(both, 'prompt', 'prompt')
        footer = self.mainframe.get_footer()
        self.mainframe.set_footer(prompt_widget)
        self.mainframe.set_focus('footer')
        self.mainloop.draw_screen()

        while True:
            keys = None
            while not keys:
                keys = self.mainloop.screen.get_input()
            for key in keys:
                if command_map[key] == 'select':
                    self.mainframe.set_footer(footer)
                    self.mainframe.set_focus('body')
                    return editpart.get_edit_text()
                if command_map[key] == 'cancel':
                    self.mainframe.set_footer(footer)
                    self.mainframe.set_focus('body')
                    return None
                else:
                    size = (20,)  # don't know why they want a size here
                    editpart.keypress(size, key)
                    self.mainloop.draw_screen()

    def commandprompt(self, startstring):
        self.logger.info('open command shell')
        mode = self.current_buffer.typename
        cmdline = self.prompt(prefix=':',
                              text=startstring,
                              completer=CommandLineCompleter(self.dbman,
                                                             self.accountman,
                                                             mode))
        if cmdline:
            cmd = interpret_commandline(cmdline, mode)
            if cmd:
                self.apply_command(cmd)
            else:
                self.notify('invalid command')

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
                self.current_buffer = buffers[index % len(buffers)]
            else:
                string = 'closing buffer %d:%s'
                self.logger.debug(string % (buffers.index(buf), buf))
                index = buffers.index(buf)
                buffers.remove(buf)

    def buffer_focus(self, buf):
        """
        focus given buffer. must be contained in self.buffers
        """
        if buf not in self.buffers:
            self.logger.error('tried to focus unknown buffer')
        else:
            self.current_buffer = buf
            self.mode = buf.typename
            if isinstance(self.current_buffer, BufferlistBuffer):
                self.current_buffer.rebuild()
            self.update()

    def get_buffers_of_type(self, t):
        return filter(lambda x: isinstance(x, t), self.buffers)

    def notify(self, statusmessage):
        self.notificationbar.set_text(statusmessage)
        if not self.show_notificationbar:
            if not self.show_statusbar:
                self.mainframe.set_footer(self.notificationbar)
            else:
                pile = self.mainframe.get_footer()
                pile.widget_list.append(self.notificationbar)
                self.mainframe.set_footer(urwid.Pile(pile.widget_list))

        def clear_notify(*args):
            self.notificationbar.set_text(' ')
            self.update()
        secs = config.getint('general', 'notify_timeout')
        self.mainloop.set_alarm_in(secs, clear_notify)

    def update(self):
        """
        redraw interface
        """
        #who needs a header?
        #head = urwid.Text('notmuch gui')
        #h=urwid.AttrMap(head, 'header')
        #self.mainframe.set_header(h)

        #body
        self.mainframe.set_body(self.current_buffer)

        #footer
        lines = []
        if self.show_statusbar:
            lines.append(self.build_statusbar())
        if self.notificationbar.get_text()[0] != ' ':
            lines.append(self.notificationbar)
        elif self.show_notificationbar:
            lines.append(urwid.Text(' '))

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

    def keypress(self, key):
        cmdline = config.get_mapping(self.mode, key)
        if cmdline:
            self.logger.debug("handle %s in %s mode" % (key, self.mode))
            if cmdline.startswith('prompt'):
                self.commandprompt(cmdline[7:])
            else:
                cmd = interpret_commandline(cmdline, self.mode)
                if cmd:
                    self.apply_command(cmd)
        else:
            self.logger.debug('unhandeled input: %s' % input)

    def apply_command(self, cmd):
        if cmd:
            if cmd.prehook:
                self.logger.debug('calling pre-hook')
                try:
                    cmd.prehook(self, self.dbman)
                except:
                    self.logger.exception('prehook failed')
            self.logger.debug('apply command: %s' % cmd)
            cmd.apply(self)
            if cmd.posthook:
                self.logger.debug('calling post-hook')
                try:
                    cmd.posthook(self, self.dbman)
                except:
                    self.logger.exception('posthook failed')
