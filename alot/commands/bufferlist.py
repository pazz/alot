# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from ..commands import Command, registerCommand
from . import globals

MODE = 'bufferlist'


@registerCommand(MODE, 'open')
class BufferFocusCommand(Command):
    """focus selected buffer"""
    def apply(self, ui):
        selected = ui.current_buffer.get_selected_buffer()
        ui.buffer_focus(selected)


@registerCommand(MODE, 'close')
class BufferCloseCommand(Command):
    """close focussed buffer"""
    def apply(self, ui):
        bufferlist = ui.current_buffer
        selected = bufferlist.get_selected_buffer()
        d = ui.apply_command(globals.BufferCloseCommand(buffer=selected))

        def cb(ignoreme):
            if bufferlist is not selected:
                bufferlist.rebuild()
            ui.update()
        d.addCallback(cb)
        return d
