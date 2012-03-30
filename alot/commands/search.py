import argparse
import logging

from alot.commands import Command, registerCommand
from alot.commands.globals import PromptCommand

from alot.db.errors import DatabaseROError
from alot import commands
from alot import buffers

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
            logging.info('open thread view for %s' % self.thread)

            sb = buffers.ThreadBuffer(ui, self.thread)
            ui.buffer_open(sb)
            sb.unfold_matching(query)


@registerCommand(MODE, 'refine', help='refine query', arguments=[
    (['--sort'], {'help':'sort order', 'choices':[
                   'oldest_first', 'newest_first', 'message_id', 'unsorted']}),
    (['query'], {'nargs':argparse.REMAINDER, 'help':'search string'})])
@registerCommand(MODE, 'sort', help='set sort order', arguments=[
    (['sort'], {'help':'sort order', 'choices':[
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
    def apply(self, ui):
        sbuffer = ui.current_buffer
        oldquery = sbuffer.querystring
        ui.apply_command(PromptCommand('refine ' + oldquery))


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
            else:
                tags.append(tag)
        initial_tagstring = ','.join(tags)
        ui.apply_command(PromptCommand('retag ' + initial_tagstring))


@registerCommand(MODE, 'tag', forced={'action': 'add'}, arguments=[
    (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                      'help': 'postpone a writeout to the index'}),
    (['tags'], {'help':'comma separated list of tags'})],
    help='add tags to all messages in the thread',
)
@registerCommand(MODE, 'retag', forced={'action': 'set'}, arguments=[
    (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                      'help': 'postpone a writeout to the index'}),
    (['tags'], {'help':'comma separated list of tags'})],
    help='set tags of all messages in the thread',
)
@registerCommand(MODE, 'untag', forced={'action': 'remove'}, arguments=[
    (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                      'help': 'postpone a writeout to the index'}),
    (['tags'], {'help':'comma separated list of tags'})],
    help='remove tags from all messages in the thread',
)
@registerCommand(MODE, 'toggletags', forced={'action': 'toggle'}, arguments=[
    (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                      'help': 'postpone a writeout to the index'}),
    (['tags'], {'help':'comma separated list of tags'})],
    help="""flip presence of tags on this thread.
    A tag is considered present if at least one message contained in this
    thread is tagged with it. In that case this command will remove the tag
    from every message in the thread.
    """)
class TagCommand(Command):
    """manipulate message tags"""
    def __init__(self, tags=u'', action='add', all=False, flush=True,
                 **kwargs):
        """
        :param tags: comma separated list of tagstrings to set
        :type tags: str
        :param action: adds tags if 'add', removes them if 'remove', adds tags
                       and removes all other if 'set' or toggle individually if
                       'toggle'
        :type action: str
        :param all: tag all messages in thread
        :type all: bool
        :param flush: imediately write out to the index
        :type flush: bool
        """
        self.tagsstring = tags
        self.all = all
        self.action = action
        self.flush = flush
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        searchbuffer = ui.current_buffer
        threadline_widget = searchbuffer.get_selected_threadline()
        # pass if the current buffer has no selected threadline
        # (displays an empty search result)
        if threadline_widget is None:
            return
        thread = threadline_widget.get_thread()
        testquery = "(%s) AND thread:%s" % (searchbuffer.querystring,
                                            thread.get_thread_id())

        def remove_thread():
            logging.debug('remove thread from result list: %s' % thread)
            if threadline_widget in searchbuffer.threadlist:
                searchbuffer.threadlist.remove(threadline_widget)
                searchbuffer.result_count -= thread.get_total_messages()

        def refresh():
            # remove thread from resultset if it doesn't match the search query
            # any more and refresh selected threadline otherwise
            if ui.dbman.count_messages(testquery) == 0:
                remove_thread()
                ui.update()
            else:
                threadline_widget.rebuild()

        tags = filter(lambda x: x, self.tagsstring.split(','))
        try:
            if self.action == 'add':
                thread.add_tags(tags, afterwards=refresh)
            if self.action == 'set':
                thread.add_tags(tags, afterwards=refresh,
                           remove_rest=True)
            elif self.action == 'remove':
                thread.remove_tags(tags, afterwards=refresh)
            elif self.action == 'toggle':
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
            ui.apply_command(commands.globals.FlushCommand())
