import argparse
import logging

from alot.commands import Command, registerCommand
from alot.commands.globals import PromptCommand

from alot.db import DatabaseROError
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


@registerCommand(MODE, 'toggletag', arguments=[
    (['tag'], {'nargs':'+', 'default':'', 'help':'tag to flip'})])
class ToggleThreadTagCommand(Command):
    """toggles given tags in all messages of a thread"""
    def __init__(self, tag, thread=None, **kwargs):
        """
        :param tag: list of tagstrings to flip
        :type tag: list of str
        :param thread: thread to edit (Uses focussed thread if unset)
        :type thread: :class:`~alot.db.Thread` or None
        """
        assert tag
        self.thread = thread
        self.tags = set(tag)
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        if not self.thread:
            return
        try:
            self.thread.set_tags(set(self.thread.get_tags()) ^ self.tags)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        # flush index
        ui.apply_command(commands.globals.FlushCommand())

        # update current buffer
        # TODO: what if changes not yet flushed?
        cb = ui.current_buffer
        if isinstance(cb, buffers.SearchBuffer):
            # refresh selected threadline
            threadwidget = cb.get_selected_threadline()
            threadwidget.rebuild()  # rebuild and redraw the line
            #remove line from searchlist if thread doesn't match the query
            qs = "(%s) AND thread:%s" % (cb.querystring,
                                         self.thread.get_thread_id())
            if ui.dbman.count_messages(qs) == 0:
                logging.debug('remove: %s' % self.thread)
                cb.threadlist.remove(threadwidget)
                cb.result_count -= self.thread.get_total_messages()
                ui.update()
        elif isinstance(cb, buffers.ThreadBuffer):
            pass


@registerCommand(MODE, 'refine', usage='refine query', arguments=[
    (['--sort'], {'help':'sort order', 'choices':[
                   'oldest_first', 'newest_first', 'message_id', 'unsorted']}),
    (['query'], {'nargs':argparse.REMAINDER, 'help':'search string'})])
@registerCommand(MODE, 'sort', usage='set sort order', arguments=[
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


@registerCommand(MODE, 'retag', arguments=[
    (['tags'], {'help':'comma separated list of tags'})])
class RetagCommand(Command):
    """overwrite a thread\'s tags"""
    def __init__(self, tags=u'', thread=None, **kwargs):
        """
        :param tags: comma separated list of tagstrings to set
        :type tags: str
        :param thread: thread to edit (Uses focussed thread if unset)
        :type thread: :class:`~alot.db.Thread` or None
        """
        self.tagsstring = tags
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        if not self.thread:
            return
        tags = filter(lambda x: x, self.tagsstring.split(','))
        logging.info("got %s:%s" % (self.tagsstring, tags))
        try:
            self.thread.set_tags(tags)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        # flush index
        ui.apply_command(commands.globals.FlushCommand())

        # refresh selected threadline
        sbuffer = ui.current_buffer
        threadwidget = sbuffer.get_selected_threadline()
        # rebuild and redraw the line
        threadwidget.rebuild()
