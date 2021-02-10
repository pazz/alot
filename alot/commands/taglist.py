# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import logging

from . import Command, registerCommand
from .globals import SearchCommand

MODE = 'taglist'


@registerCommand(MODE, 'select')
class TaglistSelectCommand(Command):

    """search for messages with selected tag"""
    async def apply(self, ui):
        try:
            tagstring = ui.current_buffer.get_selected_tag()
        except AttributeError:
            logging.debug("taglist select without tag selection")
            return
        cmd = SearchCommand(query=['tag:"%s"' % tagstring])
        await ui.apply_command(cmd)
