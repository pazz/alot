from alot.commands import Command, registerCommand

MODE = 'bufferlist'


@registerCommand(MODE, 'select')
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
        ui.buffer_close(selected)
        if bufferlist is not selected:
            bufferlist.rebuild()
        ui.update()
