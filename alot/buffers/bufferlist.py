# Copyright (C) 2011-2018  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import
import urwid

from .buffer import Buffer
from ..widgets.bufferlist import BufferlineWidget
from ..settings.const import settings


class BufferlistBuffer(Buffer):
    """lists all active buffers"""

    modename = 'bufferlist'

    def __init__(self, ui, filtfun=lambda x: x):
        self.filtfun = filtfun
        self.ui = ui
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

    def index_of(self, b):
        """
        returns the index of :class:`Buffer` `b` in the global list of active
        buffers.
        """
        return self.ui.buffers.index(b)

    def rebuild(self):
        if self.isinitialized:
            focusposition = self.bufferlist.get_focus()[1]
        else:
            focusposition = 0
            self.isinitialized = True

        lines = list()
        displayedbuffers = [b for b in self.ui.buffers if self.filtfun(b)]
        for (num, b) in enumerate(displayedbuffers):
            line = BufferlineWidget(b)
            if (num % 2) == 0:
                attr = settings.get_theming_attribute('bufferlist',
                                                      'line_even')
            else:
                attr = settings.get_theming_attribute('bufferlist', 'line_odd')
            focus_att = settings.get_theming_attribute('bufferlist',
                                                       'line_focus')
            buf = urwid.AttrMap(line, attr, focus_att)
            num = urwid.Text('%3d:' % self.index_of(b))
            lines.append(urwid.Columns([('fixed', 4, num), buf]))
        self.bufferlist = urwid.ListBox(urwid.SimpleListWalker(lines))
        num_buffers = len(displayedbuffers)
        if focusposition is not None and num_buffers > 0:
            self.bufferlist.set_focus(focusposition % num_buffers)
        self.body = self.bufferlist

    def get_selected_buffer(self):
        """returns currently selected :class:`Buffer` element from list"""
        linewidget, _ = self.bufferlist.get_focus()
        bufferlinewidget = linewidget.get_focus().original_widget
        return bufferlinewidget.get_buffer()

    def focus_first(self):
        """Focus the first line in the buffer list."""
        self.body.set_focus(0)
