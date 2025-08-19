# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import logging

from . import Command, registerCommand
from .globals import SearchCommand
from .. import commands

MODE = 'taglist'


@registerCommand(MODE, 'select')
class TaglistSelectCommand(Command):

    """search for messages with selected tag within original buffer"""
    async def apply(self, ui):
        try:
            tagstring = ui.current_buffer.get_selected_tag()
        except AttributeError:
            logging.debug("taglist select without tag selection")
            return
        if ' ' in tagstring:
            tagstring = '"%s"' % tagstring
        querystring = ui.current_buffer.querystring
        if querystring:
            fullquerystring = '(%s) AND tag:%s' % (querystring, tagstring)
        else:
            fullquerystring = 'tag:%s' % tagstring
        cmd = SearchCommand(query=[fullquerystring])
        await ui.apply_command(cmd)


@registerCommand(MODE, 'globalselect')
class TaglistGlobalSelectCommand(Command):

    """search for messages with selected tag"""
    async def apply(self, ui):
        try:
            tagstring = ui.current_buffer.get_selected_tag()
        except AttributeError:
            logging.debug("taglist globalselect without tag selection")
            return
        if ' ' in tagstring:
            tagstring = '"%s"' % tagstring
        cmd = SearchCommand(query=['tag:%s' % tagstring])
        await ui.apply_command(cmd)


@registerCommand(MODE, 'untag')
class UntagCommand(Command):

    """remove selected tag from all messages within original buffer"""
    async def apply(self, ui):
        taglistbuffer = ui.current_buffer
        taglinewidget = taglistbuffer.get_selected_tagline()
        try:
            tag = taglistbuffer.get_selected_tag()
        except AttributeError:
            logging.debug("taglist untag without tag selection")
            return
        tagstring = 'tag:"%s"' % tag
        querystring = taglistbuffer.querystring
        if querystring:
            fullquerystring = '(%s) AND %s' % (querystring, tagstring)
        else:
            fullquerystring = tagstring

        def refresh():
            if taglinewidget in taglistbuffer.taglist:
                taglistbuffer.taglist.remove(taglinewidget)
            if tag in taglistbuffer.tags:
                taglistbuffer.tags.remove(tag)
            taglistbuffer.rebuild()
            ui.update()

        try:
            ui.dbman.untag(fullquerystring, [tag])
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        await ui.apply_command(commands.globals.FlushCommand(callback=refresh))
