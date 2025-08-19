# Copyright (C) 2011-2018  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse

from . import Command, registerCommand
from .globals import ConfirmCommand
from .globals import FlushCommand
from .globals import PromptCommand
from .globals import RemoveQueryCommand
from .globals import SearchCommand
from ..db.errors import DatabaseROError

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


@registerCommand(MODE, 'query-rename', arguments=[
    (['newalias'], {'help': 'new name for the query'}),
])
class NamedqueriesRenameCommand(Command):

    """rename a query"""
    def __init__(self, newalias, **kwargs):
        self.newalias = newalias
        self.complete_count = 0

    def afterwards(self):
        self.complete_count += 1
        if self.complete_count == 2:
            self.ui.current_buffer.rebuild()

    async def apply(self, ui):
        oldalias = ui.current_buffer.get_selected_query()
        querydict = ui.dbman.get_named_queries()
        query_string = querydict[oldalias]
        self.ui = ui  # save for callback
        try:
            ui.dbman.save_named_query(self.newalias, query_string,
                                      afterwards=self.afterwards)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return
        ui.dbman.remove_named_query(oldalias, afterwards=self.afterwards)
        return await ui.apply_command(FlushCommand())


@registerCommand(MODE, 'query-duplicate', arguments=[
    (['newalias'], {'help': 'name for duplicated query', 'nargs': '?'}),
])
class NamedqueriesDuplicateCommand(Command):

    """create a copy of the query"""
    def __init__(self, newalias, **kwargs):
        self.newalias = newalias

    def afterwards(self):
        self.ui.current_buffer.rebuild()

    async def apply(self, ui):
        oldalias = ui.current_buffer.get_selected_query()
        self.newalias = self.newalias or (oldalias + '_copy')
        querydict = ui.dbman.get_named_queries()
        query_string = querydict[oldalias]
        self.ui = ui  # save for callback
        try:
            ui.dbman.save_named_query(self.newalias, query_string,
                                      afterwards=self.afterwards)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return
        return await ui.apply_command(FlushCommand())


@registerCommand(MODE, 'query-refine')
class NamedqueriesRefineCommand(Command):

    """refine a query string"""
    async def apply(self, ui):
        alias = ui.current_buffer.get_selected_query()
        query_string = ui.dbman.get_named_queries()[alias]
        await ui.apply_command(PromptCommand('savequery {} {}'.format(
            alias, query_string)))
        ui.current_buffer.rebuild()


@registerCommand(MODE, 'query-remove')
class NamedqueriesRemoveCommand(Command):

    def afterwards(self):
        self.ui.current_buffer.rebuild()

    """remove the selected namedquery"""
    async def apply(self, ui):
        self.ui = ui
        alias = ui.current_buffer.get_selected_query()
        await ui.apply_command(ConfirmCommand(
            msg=['Remove named query {}'.format(alias)]))
        # SequenceCanceled raised if not confirmed
        await ui.apply_command(
            RemoveQueryCommand(alias, afterwards=self.afterwards))
