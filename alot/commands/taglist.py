from commands import Command, registerCommand
from twisted.internet import defer

class TaglistSelectCommand(Command):
    def apply(self, ui):
        tagstring = ui.current_buffer.get_selected_tag()
        cmd = SearchCommand(query='tag:%s' % tagstring)
        ui.apply_command(cmd)
