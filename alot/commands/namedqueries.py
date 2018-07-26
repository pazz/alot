# Copyright (C) 2011-2018  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse

from . import Command, registerCommand
from .globals import SearchCommand

MODE = 'namedqueries'


@registerCommand(MODE, 'select', arguments=[
    (['filt'], {'nargs': argparse.REMAINDER,
                'help': 'additional filter to apply to query'}),
])
class NamedqueriesSelectCommand(Command):

    """search for messages with selected query"""
    def __init__(self, filt=None, **kwargs):
        self._filt = filt
        Command.__init__(self, **kwargs)

    async def apply(self, ui):
        query_name = ui.current_buffer.get_selected_query()
        query = ['query:"%s"' % query_name]
        if self._filt:
            query.extend(['and'] + self._filt)

        cmd = SearchCommand(query=query)
        await ui.apply_command(cmd)
