# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse
import logging

from . import Command, registerCommand
from .globals import PromptCommand
from .globals import SaveQueryCommand as GlobalSaveQueryCommand
from .common import RetagPromptCommand
from .. import commands

from .. import buffers
from ..db.errors import DatabaseROError
from ..settings.const import settings


MODE = 'search'
_NO_FLUSH_ARG = (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                                  'help': 'postpone a writeout to the index'})
_TAGS_ARG = (['tags'], {'help': 'comma separated list of tags'})


def _all_arg(help):
    return (['--all'], {'action': 'store_true', 'dest': 'allmessages',
                        'default': False, 'help': help})


@registerCommand(
    MODE, 'select',
    arguments=[
        (['--all-folded'], {'action': 'store_true',
                            'dest': 'all_folded',
                            'help': 'do not unfold matching messages'}),
    ],
)
class OpenThreadCommand(Command):

    """open thread in a new buffer"""
    def __init__(self, thread=None, all_folded=False):
        """
        :param thread: thread to open (Uses focussed thread if unset)
        :type thread: :class:`~alot.db.Thread`
        """
        self.thread = thread
        self.all_folded = all_folded

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        if self.thread:
            query = settings.get('thread_unfold_matching')
            if not query:
                query = ui.current_buffer.querystring
            logging.info('open thread view for %s', self.thread)

            tb = buffers.ThreadBuffer(ui, self.thread)
            ui.buffer_open(tb)
            if not self.all_folded:
                tb.unfold_matching(query)


@registerCommand(MODE, 'refine', help='refine query', arguments=[
    (['--sort'], {'help': 'sort order', 'choices': [
        'oldest_first', 'newest_first', 'message_id', 'unsorted']}),
    (['--limit'], {'help': 'limit number of results', 'type': int}),
    (['query'], {'nargs': argparse.REMAINDER, 'help': 'search string'})])
@registerCommand(MODE, 'sort', help='set sort order', arguments=[
    (['sort'], {'help': 'sort order', 'choices': [
        'oldest_first', 'newest_first', 'message_id', 'unsorted']}),
])
@registerCommand(MODE, 'limit', help='limit number of results', arguments=[
    (['limit'], {'help': 'the thread count limit', 'type': int}),
])
class RefineCommand(Command):

    """refine the querystring of this buffer"""
    def __init__(self, query=None, sort=None, limit=None):
        """
        :param query: new querystring given as list of strings as returned by
                      argparse
        :type query: list of str
        :param sort: how to order results. Must be one of
                     'oldest_first', 'newest_first', 'message_id' or
                     'unsorted'.
        :type sort: str
        :param limit: limit the number of results
        :type limit: int
        """
        if query is None:
            self.querystring = None
        else:
            self.querystring = ' '.join(query)
        self.sort_order = sort
        self.limit = limit

    def apply(self, ui):
        if self.querystring or self.sort_order or self.limit is not None:
            sbuffer = ui.current_buffer
            oldquery = sbuffer.querystring
            if self.querystring not in [None, oldquery]:
                sbuffer.querystring = self.querystring
                sbuffer = ui.current_buffer
            if self.sort_order:
                sbuffer.sort_order = self.sort_order
            if self.limit not in [None, sbuffer.limit]:
                sbuffer.limit = self.limit
                sbuffer = ui.current_buffer
            sbuffer.rebuild()
            ui.update()
        else:
            ui.notify('empty query string')


@registerCommand(MODE, 'refineprompt')
class RefinePromptCommand(Command):

    """prompt to change this buffers querystring"""
    repeatable = True

    async def apply(self, ui):
        sbuffer = ui.current_buffer
        oldquery = sbuffer.querystring
        return await ui.apply_command(PromptCommand('refine ' + oldquery))


RetagPromptCommand = registerCommand(MODE, 'retagprompt')(RetagPromptCommand)


@registerCommand(
    MODE, 'tag', forced={'action': 'add'},
    arguments=[_NO_FLUSH_ARG, _all_arg(
        'tag all messages that match the current search query'), _TAGS_ARG],
    help='add tags to all messages in the selected thread',
)
@registerCommand(
    MODE, 'retag', forced={'action': 'set'},
    arguments=[_NO_FLUSH_ARG, _all_arg(
        'retag all messages that match the current query'), _TAGS_ARG],
    help='set tags to all messages in the selected thread',
)
@registerCommand(
    MODE, 'untag', forced={'action': 'remove'},
    arguments=[_NO_FLUSH_ARG, _all_arg(
        'untag all messages that match the current query'), _TAGS_ARG],
    help='remove tags from all messages in the selected thread',
)
@registerCommand(
    MODE, 'toggletags', forced={'action': 'toggle'},
    arguments=[_NO_FLUSH_ARG, _TAGS_ARG],
    help='flip presence of tags on the selected thread: a tag is considered present '
         'and will be removed if at least one message in this thread is '
         'tagged with it')
class TagCommand(Command):

    """manipulate message tags"""
    repeatable = True

    def __init__(self, tags='', action='add', allmessages=False, flush=True):
        """
        :param tags: comma separated list of tagstrings to set
        :type tags: str
        :param action: adds tags if 'add', removes them if 'remove', adds tags
                       and removes all other if 'set' or toggle individually if
                       'toggle'
        :type action: str
        :param allmessages: tag all messages in search result
        :type allmessages: bool
        :param flush: immediately write out to the index
        :type flush: bool
        """
        self.tagsstring = tags
        self.action = action
        self.allm = allmessages
        self.flush = flush

    async def apply(self, ui):
        searchbuffer = ui.current_buffer
        threadline_widget = searchbuffer.get_selected_threadline()
        # pass if the current buffer has no selected threadline
        # (displays an empty search result)
        if threadline_widget is None:
            return

        testquery = searchbuffer.querystring
        thread = threadline_widget.get_thread()
        if not self.allm:
            testquery = "thread:%s" % thread.get_thread_id()
        logging.debug('all? %s', self.allm)
        logging.debug('q: %s', testquery)

        def refresh_now():
            if not self.allm:
                searchbuffer.refresh_threadline(threadline_widget)
            else:
                searchbuffer.rebuild()

            ui.update()

        def refresh():
            # keep the threadline until the whole command line has run,
            # so that later commands in a sequence act on the same thread
            ui.defer(refresh_now)

        tags = [x for x in self.tagsstring.split(',') if x]

        try:
            if self.action == 'add':
                ui.dbman.tag(testquery, tags, remove_rest=False)
            if self.action == 'set':
                ui.dbman.tag(testquery, tags, remove_rest=True)
            elif self.action == 'remove':
                ui.dbman.untag(testquery, tags)
            elif self.action == 'toggle':
                if not self.allm:
                    ui.dbman.toggle_tags(testquery, tags, afterwards=refresh)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        # flush index
        if self.flush:
            await ui.apply_command(
                commands.globals.FlushCommand(callback=refresh))


@registerCommand(
    MODE, 'savequery',
    arguments=[
        _NO_FLUSH_ARG,
        (['alias'], {'help': 'alias to use for query string'}),
        (['query'], {'help': 'query string to store',
                     'nargs': argparse.REMAINDER,
                     }),
    ],
    help='store query string as a "named query" in the database. '
         'This falls back to the current search query in search buffers.')
class SaveQueryCommand(GlobalSaveQueryCommand):
    async def apply(self, ui):
        searchbuffer = ui.current_buffer
        if not self.query:
            self.query = searchbuffer.querystring
        await GlobalSaveQueryCommand.apply(self, ui)
