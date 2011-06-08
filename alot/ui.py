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

from settings import config
from settings import get_palette
import command
from widgets import PromptWidget
from buffer import BufferListBuffer


class UI:
    buffers = []
    current_buffer = None

    def __init__(self, db, log, initialquery, colourmode):
        self.logger = log
        self.dbman = db

        if not colourmode:
            colourmode = config.getint('general', 'colourmode')
        self.logger.info('setup gui in %d colours' % colourmode)
        self.mainframe = urwid.Frame(urwid.SolidFill(' '))
        self.mainloop = urwid.MainLoop(self.mainframe,
                get_palette(),
                handle_mouse=False,
                unhandled_input=self.keypress)
        self.mainloop.screen.set_terminal_properties(colors=colourmode)

        self.logger.debug('setup bindings')
        self.bindings = {
            'I': ('search', {'query': 'tag:inbox AND NOT tag:killed'}),
            'U': ('search', {'query': 'tag:unread'}),
            'x': ('buffer_close', {}),
            'tab': ('buffer_next', {}),
            'shift tab': ('buffer_prev', {}),
            '\\': ('search_prompt', {}),
            'q': ('shutdown', {}),
            ';': ('buffer_list', {}),
            'L': ('open_taglist', {}),
            's': ('shell', {}),
            'v': ('view_log', {}),
            '@': ('refresh_buffer', {}),
        }
        cmd = command.factory('search', query=initialquery)
        self.apply_command(cmd)
        self.mainloop.run()

    def shutdown(self):
        """
        close the ui. this is _not_ the main shutdown procedure:
        there is a shutdown command that will eventually call this.
        """
        raise urwid.ExitMainLoop()

    def prompt(self, prefix='>', text='', completer=None):
        self.logger.info('open prompt')

        prefix_widget = PromptWidget(prefix, text, completer)
        footer = self.mainframe.get_footer()
        self.mainframe.set_footer(prefix_widget)
        self.mainframe.set_focus('footer')
        self.mainloop.draw_screen()
        while True:
            keys = None
            while not keys:
                keys = self.mainloop.screen.get_input()
            for key in keys:
                if key == 'enter':
                    self.mainframe.set_footer(footer)
                    self.mainframe.set_focus('body')
                    return prefix_widget.get_input()
                if key == 'esc':
                    self.mainframe.set_footer(footer)
                    self.mainframe.set_focus('body')
                    return None
                else:
                    size = (20,)  # don't know why they want a size here
                    prefix_widget.keypress(size, key)
                    self.mainloop.draw_screen()

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
            cmd = command.factory('shutdown')
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
            if isinstance(self.current_buffer, BufferListBuffer):
                self.current_buffer.rebuild()
            self.update()

    def get_buffers_of_type(self, t):
        return filter(lambda x: isinstance(x, t), self.buffers)

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
        self.update_footer()

    def update_footer(self):
        idx = self.buffers.index(self.current_buffer)
        lefttxt = '%d: [%s] %s' % (idx, self.current_buffer.typename,
                                 self.current_buffer)
        footerleft = urwid.Text(lefttxt, align='left')
        righttxt = 'total messages: %d' % self.dbman.count_messages('*')
        footerright = urwid.Text(righttxt, align='right')
        columns = urwid.Columns([
            footerleft,
            ('fixed', len(righttxt), footerright)])
        footer = urwid.AttrMap(columns, 'footer')
        self.mainframe.set_footer(footer)

    def keypress(self, key):
        if key in self.bindings:
            self.logger.debug("got globally bounded key: %s" % key)
            (cmdname, parms) = self.bindings[key]
            cmd = command.factory(cmdname, **parms)
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
