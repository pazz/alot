from alot.commands import Command, registerCommand
from twisted.internet import defer


from alot.db import DatabaseROError
from alot import commands
from alot import buffers

MODE = 'search'


@registerCommand(MODE, 'openthread', {})  # todo: make this select
class OpenThreadCommand(Command):
    """open a new thread-view buffer"""
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


@registerCommand(MODE, 'toggletag', {})
class ToggleThreadTagCommand(Command):
    """toggles tag in given or currently selected thread"""
    def __init__(self, tags, thread=None, **kwargs):
        assert tags
        self.thread = thread
        self.tags = set(tags)
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


@registerCommand(MODE, 'refine', arguments=[
    (['query'], {'nargs':'*', 'default':'', 'help':'search string'})]
)
class RefineCommand(Command):
    """refine the query of the currently open searchbuffer"""
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


@registerCommand(MODE, 'refineprompt', {})
class RefinePromptCommand(Command):
    """prompt to change current search buffers query"""
    def apply(self, ui):
        sbuffer = ui.current_buffer
        oldquery = sbuffer.querystring
        ui.commandprompt('refine ' + oldquery)


@registerCommand(MODE, 'retagprompt', {})
class RetagPromptCommand(Command):
    """start a commandprompt to retag selected threads' tags
    this is needed to fill the prompt with the current tags..
    """
    def apply(self, ui):
        thread = ui.current_buffer.get_selected_thread()
        if not thread:
            return
        initial_tagstring = ','.join(thread.get_tags())
        ui.commandprompt('retag ' + initial_tagstring)


@registerCommand(MODE, 'retag', {})
class RetagCommand(Command):
    """tag selected thread"""
    def __init__(self, tagsstring=u'', thread=None, **kwargs):
        self.tagsstring = tagsstring
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
        threadwidget.rebuild()  # rebuild and redraw the line
