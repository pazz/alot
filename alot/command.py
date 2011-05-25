import os
import code
import logging
import threading
import subprocess

import buffer
import hooks
import settings


class Command:
    """base class for commands"""
    def __init__(self, prehook=None, posthook=None):
        self.prehook = prehook
        self.posthook = posthook
        self.undoable = False
        self.help = self.__doc__

    def apply(self, caller):
        pass


class ShutdownCommand(Command):
    """shuts the MUA down cleanly"""
    def apply(self, ui):
        ui.shutdown()


class OpenThreadCommand(Command):
    """open a new thread-view buffer"""
    def __init__(self, thread, **kwargs):
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ui.logger.info('open thread view for %s' % self.thread)
        sb = buffer.SingleThreadBuffer(ui, self.thread)
        ui.buffer_open(sb)


class SearchCommand(Command):
    """open a new search buffer"""
    def __init__(self, query, **kwargs):
        """
        @param query initial querystring
        """
        self.query = query
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        sb = buffer.SearchBuffer(ui, self.query)
        ui.buffer_open(sb)


class SearchPromptCommand(Command):
    """prompt the user for a querystring, then start a search"""
    def apply(self, ui):
        querystring = ui.prompt('search threads:')
        ui.logger.info("got %s" % querystring)
        if querystring:
            cmd = factory('search', query=querystring)
            ui.apply_command(cmd)


class EditCommand(Command):
    """
    opens editor
    TODO tempfile handling etc
    """
    def __init__(self, path, spawn=False, **kwargs):
        self.path = path
        self.spawn = settings.spawn_editor or spawn
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        def afterwards():
            ui.logger.info('Editor was closed')
        cmd = ExternalCommand(settings.editor_cmd % self.path,
                              spawn=self.spawn,
                              onExit=afterwards)
        ui.apply_command(cmd)


class PagerCommand(Command):
    """opens pager"""

    def __init__(self, path, spawn=False, **kwargs):
        self.path = path
        self.spawn = settings.spawn_pager or spawn
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        def afterwards():
            ui.logger.info('pager was closed')
        cmd = ExternalCommand(settings.pager_cmd %self.path,
                              spawn=self.spawn,
                              onExit=afterwards)
        ui.apply_command(cmd)


class ExternalCommand(Command):
    """calls external command"""
    def __init__(self, commandstring, spawn=False, refocus=True, onExit=None, **kwargs):
        self.commandstring = commandstring
        self.spawn = spawn
        self.refocus = refocus
        self.onExit = onExit
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        def call(onExit, popenArgs):
            callerbuffer = ui.current_buffer
            ui.logger.info('CALLERBUFFER: %s'%callerbuffer)
            proc = subprocess.Popen(*popenArgs,shell=True)
            proc.wait()
            if callable(onExit):
                onExit()
            if self.refocus and callerbuffer in ui.buffers:
                ui.logger.info('TRY TO REFOCUS: %s'%callerbuffer)
                ui.buffer_focus(callerbuffer)
            return

        if self.spawn:
            cmd = settings.terminal_cmd % self.commandstring
            thread = threading.Thread(target=call, args=(self.onExit, (cmd,)))
            thread.start()
        else:
            ui.mainloop.screen.stop()
            cmd = self.commandstring
            logging.debug(cmd)
            call(self.onExit,(cmd,))
            ui.mainloop.screen.start()

class OpenPythonShellCommand(Command):
    """
    opens an interactive shell for introspection
    """
    def apply(self, ui):
        ui.mainloop.screen.stop()
        code.interact(local=locals())
        ui.mainloop.screen.start()


class BufferCloseCommand(Command):
    """
    close a buffer
    @param buffer the selected buffer
    """
    def __init__(self, buffer=None, **kwargs):
        self.buffer = buffer
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.buffer:
            self.buffer = ui.current_buffer
        ui.buffer_close(self.buffer)
        ui.buffer_focus(ui.current_buffer)


class BufferFocusCommand(Command):
    """
    focus a buffer
    @param buffer the selected buffer
    """
    def __init__(self, buffer=None, offset=0, **kwargs):
        self.buffer = buffer
        self.offset = offset
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.buffer:
            self.buffer = ui.current_buffer
        i = ui.buffers.index(self.buffer)
        l = len(ui.buffers)
        ui.buffer_focus(ui.buffers[(i + self.offset) % l])


class BufferListCommand(Command):
    """
    open a bufferlist
    """
    def __init__(self, filtfun=None, **kwargs):
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        b = buffer.BufferListBuffer(ui, self.filtfun)
        ui.buffers.append(b)
        b.rebuild()
        ui.buffer_focus(b)

class TagListCommand(Command):
    """
    open a taglist
    """
    def __init__(self, filtfun=None, **kwargs):
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        tags = ui.dbman.get_all_tags()
        b = buffer.TagListBuffer(ui, tags, self.filtfun)
        ui.buffers.append(b)
        b.rebuild()
        ui.buffer_focus(b)


class ToggleThreadTagCommand(Command):
    """
    opens editor
    TODO tempfile handling etc
    """
    def __init__(self, thread, tag, **kwargs):
        self.thread = thread
        self.tag = tag
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.tag in self.thread.get_tags():
            ui.dbman.untag_thread(self.thread, [self.tag])
        else:
            ui.dbman.tag_thread(self.thread, [self.tag])
        #refresh selected threadline
        widget = ui.current_buffer.get_selected_threadline()
        widget.reload_tag(ui.dbman) #threads seem to cache their tags
        widget.rebuild() #rebuild and redraw the line
        #TODO: remove line from searchlist if thread doesn't match the query

commands = {
        'buffer_close': (BufferCloseCommand, {}),
        'buffer_list': (BufferListCommand, {}),
        'buffer_focus': (BufferFocusCommand, {}),
        'buffer_next': (BufferFocusCommand, {'offset': 1}),
        'buffer_prev': (BufferFocusCommand, {'offset': -1}),
        'open_inbox': (SearchCommand, {'query': 'tag:inbox'}),
        'open_unread': (SearchCommand, {'query': 'tag:unread'}),
        'open_search': (SearchPromptCommand, {}),
        'open_thread': (OpenThreadCommand, {}),
        'search': (SearchCommand, {}),
        'shutdown': (ShutdownCommand, {}),
        'shell': (OpenPythonShellCommand, {}),
        'view_log': (PagerCommand, {'path': 'debug.log'}),
        'call_editor': (EditCommand, {}),
        'call_pager': (PagerCommand, {}),
        'open_taglist': (TagListCommand, {}),
        'toggle_thread_tag': (ToggleThreadTagCommand, {'tag': 'inbox'})
        }


def factory(cmdname, **kwargs):
    if cmdname in commands:
        (cmdclass, parms) = commands[cmdname]
        parms = parms.copy()
        parms.update(kwargs)
        for (key, value) in kwargs.items():
            if callable(value):
                try:
                    parms[key] = value()
                except:
                    parms[key] = None
            else:
                parms[key] = value
        prehook = hooks.get_hook('pre-' + cmdname)
        if prehook:
            parms['prehook'] = prehook

        posthook = hooks.get_hook('post-' + cmdname)
        if posthook:
            parms['posthook'] = hooks.get_hook('post-' + cmdname)

        logging.debug('cmd parms %s' % parms)
        return cmdclass(**parms)
    else:
        logging.error('there is no command %s' % cmdname)
