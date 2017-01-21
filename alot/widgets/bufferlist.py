# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""
Widgets specific to Bufferlist mode
"""
from __future__ import absolute_import

import urwid


class BufferlineWidget(urwid.Text):
    """
    selectable text widget that represents a :class:`~alot.buffers.Buffer`
    in the :class:`~alot.buffers.BufferlistBuffer`.
    """

    def __init__(self, buffer):
        self.buffer = buffer
        line = buffer.__str__()
        urwid.Text.__init__(self, line, wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_buffer(self):
        return self.buffer
