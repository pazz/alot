from alot.commands import Command, registerCommand
from twisted.internet import defer
import argparse


from alot.db import DatabaseROError
from alot import commands
from alot import buffers

MODE = 'search'


@registerCommand(MODE, 'select',
                 help='open a new thread buffer')
class OpenThreadCommand(Command):
    def __init__(self, thread=None, **kwargs):
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        if self.thread:
            query = ui.current_buffer.querystring
            ui.logger.info('open thread view for %s' % self.thread)

            sb = buffers.ThreadBuffer(ui, self.thread)
            ui.buffer_open(sb)
            sb.unfold_matching(query)


@registerCommand(MODE, 'toggletag', arguments=[
    (['tag'], {'nargs':'+', 'default':'', 'help':'tag to flip'})],
    help='toggles tags in selected thread')
class ToggleThreadTagCommand(Command):
    def __init__(self, tag, thread=None, **kwargs):
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
                ui.logger.debug('remove: %s' % self.thread)
                cb.threadlist.remove(threadwidget)
                cb.result_count -= self.thread.get_total_messages()
                ui.update()
        elif isinstance(cb, buffers.ThreadBuffer):
            pass


@registerCommand(MODE, 'refine', usage='refine query', arguments=[
    (['query'], {'nargs':argparse.REMAINDER, 'help':'search string'})],
    help='refine the query of the currently open searchbuffer')
class RefineCommand(Command):
    def __init__(self, query=None, **kwargs):
        self.querystring = ' '.join(query)
        Command.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def apply(self, ui):
        if self.querystring:
            if self.querystring == '*':
                s = 'really search for all threads? This takes a while..'
                if (yield ui.choice(s, select='yes', cancel='no')) == 'no':
                    return
            sbuffer = ui.current_buffer
            oldquery = sbuffer.querystring
            if self.querystring not in [None, oldquery]:
                sbuffer.querystring = self.querystring
                sbuffer = ui.current_buffer
                sbuffer.rebuild()
                ui.update()
        else:
            ui.notify('empty query string')


@registerCommand(MODE, 'refineprompt',
                 help='prompt to change current search buffers query')
class RefinePromptCommand(Command):
    def apply(self, ui):
        sbuffer = ui.current_buffer
        oldquery = sbuffer.querystring
        ui.commandprompt('refine ' + oldquery)


@registerCommand(MODE, 'retagprompt',
                 help='prompt to retag selected threads\' tags')
class RetagPromptCommand(Command):
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
        ui.commandprompt('retag ' + initial_tagstring)


@registerCommand(MODE, 'retag', arguments=[
    (['tags'], {'help':'comma separated list of tags'})],
                 help='overwrite selected thread\'s tags')
class RetagCommand(Command):
    def __init__(self, tags=u'', thread=None, **kwargs):
        self.tagsstring = tags
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        if not self.thread:
            return
        tags = filter(lambda x: x, self.tagsstring.split(','))
        ui.logger.info("got %s:%s" % (self.tagsstring, tags))
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
