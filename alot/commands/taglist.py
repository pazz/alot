from commands import Command, registerCommand

import commands

MODE = 'taglist'


@registerCommand(MODE, 'select', {})
class TaglistSelectCommand(Command):
    def apply(self, ui):
        tagstring = ui.current_buffer.get_selected_tag()
        cmd = commands.globals.SearchCommand(query='tag:%s' % tagstring)
        ui.apply_command(cmd)


