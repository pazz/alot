from command import Command, registerCommand
#from alot.command import Command, registerCommand
from twisted.internet import defer

registerCommand('global', 'exit', {})
class ExitCommand(Command):
    """shuts the MUA down cleanly"""
    @defer.inlineCallbacks
    def apply(self, ui):
        if settings.config.getboolean('general', 'bug_on_exit'):
            if (yield ui.choice('realy quit?', select='yes', cancel='no',
                               msg_position='left')) == 'no':
                return
        ui.exit()


registerCommand('global', 'search', {})
class SearchCommand(Command):
    """open a new search buffer"""
    def __init__(self, query, **kwargs):
        """
        :param query: initial querystring
        """
        self.query = query
        Command.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def apply(self, ui):
        if self.query:
            if self.query == '*' and ui.current_buffer:
                s = 'really search for all threads? This takes a while..'
                if (yield ui.choice(s, select='yes', cancel='no')) == 'no':
                    return
            open_searches = ui.get_buffers_of_type(buffer.SearchBuffer)
            to_be_focused = None
            for sb in open_searches:
                if sb.querystring == self.query:
                    to_be_focused = sb
            if to_be_focused:
                ui.buffer_focus(to_be_focused)
            else:
                ui.buffer_open(buffer.SearchBuffer(ui, self.query))
        else:
            ui.notify('empty query string')

