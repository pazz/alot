from alot.commands import Command, registerCommand
from alot import buffers

MODE = 'bufferlist'


@registerCommand(MODE, 'select', help='focus selected buffer')
class BufferFocusCommand(Command):
    def apply(self, ui):
        selected = ui.current_buffer.get_selected_buffer()
        ui.buffer_focus(selected)


@registerCommand(MODE, 'close', help='close focussed buffer')
class BufferCloseCommand(Command):
    def apply(self, ui):
        selected = ui.current_buffer.get_selected_buffer()
        if isinstance(selected, buffers.SearchBuffer):
            selected.kill_filler_process()
        ui.buffer_close(selected)
        ui.buffer_focus(ui.current_buffer)
