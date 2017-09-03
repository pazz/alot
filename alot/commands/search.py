# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import argparse
import logging

from . import Command, registerCommand
from .globals import PromptCommand
from .globals import MoveCommand
from .. import commands

from .. import buffers
from ..db.errors import DatabaseROError


MODE = 'search'


@registerCommand(MODE, 'select')
class OpenThreadCommand(Command):

    """open thread in a new buffer"""
    def __init__(self, thread=None, **kwargs):
        """
        :param thread: thread to open (Uses focussed thread if unset)
        :type thread: :class:`~alot.db.Thread`
        """
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        if self.thread:
            query = ui.current_buffer.querystring
            logging.info('open thread view for %s', self.thread)

            sb = buffers.ThreadBuffer(ui, self.thread)
            ui.buffer_open(sb)
            sb.unfold_matching(query)


@registerCommand(MODE, 'refine', help='refine query', arguments=[
    (['--sort'], {'help': 'sort order', 'choices': [
        'oldest_first', 'newest_first', 'message_id', 'unsorted']}),
    (['query'], {'nargs': argparse.REMAINDER, 'help': 'search string'})])
@registerCommand(MODE, 'sort', help='set sort order', arguments=[
    (['sort'], {'help': 'sort order', 'choices': [
        'oldest_first', 'newest_first', 'message_id', 'unsorted']}),
])
class RefineCommand(Command):

    """refine the querystring of this buffer"""
    def __init__(self, query=None, sort=None, **kwargs):
        """
        :param query: new querystring given as list of strings as returned by
                      argparse
        :type query: list of str
        """
        if query is None:
            self.querystring = None
        else:
            self.querystring = ' '.join(query)
        self.sort_order = sort
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.querystring or self.sort_order:
            sbuffer = ui.current_buffer
            oldquery = sbuffer.querystring
            if self.querystring not in [None, oldquery]:
                sbuffer.querystring = self.querystring
                sbuffer = ui.current_buffer
            if self.sort_order:
                sbuffer.sort_order = self.sort_order
            sbuffer.rebuild()
            ui.update()
        else:
            ui.notify('empty query string')


@registerCommand(MODE, 'refineprompt')
class RefinePromptCommand(Command):

    """prompt to change this buffers querystring"""
    repeatable = True

    def apply(self, ui):
        sbuffer = ui.current_buffer
        oldquery = sbuffer.querystring
        return ui.apply_command(PromptCommand('refine ' + oldquery))


@registerCommand(MODE, 'retagprompt')
class RetagPromptCommand(Command):

    """prompt to retag selected threads\' tags"""
    def apply(self, ui):
        thread = ui.current_buffer.get_selected_thread()
        if not thread:
            return
        tags = []
        for tag in thread.get_tags():
            if ' ' in tag:
                tags.append('"%s"' % tag)
            # skip empty tags
            elif tag:
                tags.append(tag)
        initial_tagstring = ','.join(sorted(tags)) + ','
        return ui.apply_command(PromptCommand('retag ' + initial_tagstring))


@registerCommand(
    MODE, 'tag', forced={'action': 'add'},
    arguments=[
        (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                          'default': 'True',
                          'help': 'postpone a writeout to the index'}),
        (['--all'], {'action': 'store_true', 'dest': 'allmessages', 'default':
                     False, 'help': 'retag all messages in search result'}),
        (['tags'], {'help': 'comma separated list of tags'})],
    help='add tags to all messages in the thread that match the current query',
)
@registerCommand(
    MODE, 'retag', forced={'action': 'set'},
    arguments=[
        (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                          'default': 'True',
                          'help': 'postpone a writeout to the index'}),
        (['--all'], {'action': 'store_true', 'dest': 'allmessages', 'default':
                     False, 'help': 'retag all messages in search result'}),
        (['tags'], {'help': 'comma separated list of tags'})],
    help='set tags of all messages in the thread that match the current query',
)
@registerCommand(
    MODE, 'untag', forced={'action': 'remove'},
    arguments=[
        (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                          'default': 'True',
                          'help': 'postpone a writeout to the index'}),
        (['--all'], {'action': 'store_true', 'dest': 'allmessages', 'default':
                     False, 'help': 'retag all messages in search result'}),
        (['tags'], {'help': 'comma separated list of tags'})],
    help='remove tags from all messages in the thread that match the query',
)
@registerCommand(
    MODE, 'toggletags', forced={'action': 'toggle'},
    arguments=[
        (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                          'default': 'True',
                          'help': 'postpone a writeout to the index'}),
        (['tags'], {'help': 'comma separated list of tags'})],
    help='flip presence of tags on this thread. A tag is considered present '
         'if at least one message contained in this thread is tagged with it. '
         'In that case this command will remove the tag from every message in '
         'the thread.')
class TagCommand(Command):

    """manipulate message tags"""
    repeatable = True

    def __init__(self, tags=u'', action='add', allmessages=False, flush=True,
                 **kwargs):
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
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        searchbuffer = ui.current_buffer
        threadline_widget = searchbuffer.get_selected_threadline()
        # pass if the current buffer has no selected threadline
        # (displays an empty search result)
        if threadline_widget is None:
            return

        testquery = searchbuffer.querystring
        thread = threadline_widget.get_thread()
        if not self.allm:
            testquery = "(%s) AND thread:%s" % (testquery,
                                                thread.get_thread_id())
        logging.debug('all? %s', self.allm)
        logging.debug('q: %s', testquery)

        def refresh():
            # remove thread from resultset if it doesn't match the search query
            # any more and refresh selected threadline otherwise
            hitcount_after = ui.dbman.count_messages(testquery)
            # update total result count
            if not self.allm:
                if hitcount_after == 0:
                    logging.debug('remove thread from result list: %s', thread)
                    if threadline_widget in searchbuffer.threadlist:
                        # remove this thread from result list
                        searchbuffer.threadlist.remove(threadline_widget)
                else:
                    threadline_widget.rebuild()
                searchbuffer.result_count = searchbuffer.dbman.count_messages(
                    searchbuffer.querystring)
            else:
                searchbuffer.rebuild()

            ui.update()

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
                    to_remove = []
                    to_add = []
                    for t in tags:
                        if t in thread.get_tags():
                            to_remove.append(t)
                        else:
                            to_add.append(t)
                    thread.remove_tags(to_remove)
                    thread.add_tags(to_add, afterwards=refresh)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        # flush index
        if self.flush:
            ui.apply_command(commands.globals.FlushCommand(callback=refresh))


@registerCommand(
    MODE, 'move', help='move focus in search buffer',
    arguments=[(['movement'], {'nargs': argparse.REMAINDER, 'help': 'last'})])
class MoveFocusCommand(MoveCommand):

    def apply(self, ui):
        logging.debug(self.movement)
        if self.movement == 'last':
            ui.current_buffer.focus_last()
            ui.update()
        else:
            MoveCommand.apply(self, ui)
