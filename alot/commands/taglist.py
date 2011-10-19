from alot.commands import Command, registerCommand
from alot.commands.globals import SearchCommand

MODE = 'taglist'


@registerCommand(MODE, 'select', help='open search for selected tag')
class TaglistSelectCommand(Command):
    def apply(self, ui):
        tagstring = ui.current_buffer.get_selected_tag()
        cmd = SearchCommand(query=['tag:"%s"' % tagstring])
        ui.apply_command(cmd)
