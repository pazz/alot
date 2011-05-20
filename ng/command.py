import urwid
import logging
import buffer
import hooks

class Command:
    """ base class for commands """
    def __init__(self,prehook=None,posthook=None):
        self.prehook = prehook
        self.posthook = posthook
        self.undoable = False
        self.help = self.__doc__
    def apply(self,caller):
        return

class ShutdownCommand(Command):
    """ shuts the MUA down cleanly """
    def apply(self,ui):
        ui.shutdown()

class SearchCommand(Command):
    """
    open a new search buffer
    @param query initial querystring
    """
    def __init__(self,query,**kwargs):
        self.query = query
        Command.__init__(self,**kwargs)
    def apply(self,ui):
        sb = buffer.SearchBuffer(ui,self.query)
        ui.buffer_open(sb)

class SearchPromptCommand(Command):
    """
    prompt the user for a querystring, then start a search
    """
    def apply(self,ui):
        querystring = ui.prompt('search threads:')
        ui.logger.info("got %s"%querystring)
        if querystring:
            cmd = factory('search',query=querystring)
            ui.apply_command(cmd)

class EditCommand(Command):
    """
    opens editor
    TODO tempfile handling etc
    """
    def apply(self,ui):
        #import shlex,subprocess
        import os
        cmd = "vim ng.log"
        #args = shlex.split(cmd)
        ui.logger.info('call editor')
        #ui.logger.debug(args)
        ui.mainloop.screen.stop()
        os.system(cmd)
        #p = subprocess.Popen(args)
        ui.mainloop.screen.start()

class OpenPythonShellCommand(Command):
    """
    opens an interactive shell for introspection
    """
    def apply(self,ui):
        import code
        ui.mainloop.screen.stop()
        code.interact(local=locals())
        ui.mainloop.screen.start()

class BufferCloseCommand(Command):
    """
    close a buffer
    @param buffer the selected buffer
    """
    def __init__(self,buffer=None,**kwargs):
        self.buffer = buffer
        Command.__init__(self,**kwargs)
    def apply(self,ui):
        if not self.buffer:
            self.buffer=ui.current_buffer
        ui.buffer_close(self.buffer)
        ui.buffer_focus(ui.current_buffer)

class BufferFocusCommand(Command):
    """
    focus a buffer
    @param buffer the selected buffer
    """
    def __init__(self,buffer=None,offset=0,**kwargs):
        self.buffer = buffer
        self.offset = offset
        Command.__init__(self,**kwargs)
    def apply(self,ui):
        if not self.buffer:
            self.buffer=ui.current_buffer
        i = ui.buffers.index(self.buffer)
        l = len(ui.buffers)
        ui.buffer_focus(ui.buffers[(i+self.offset)%l])

class BufferListCommand(Command):
    """
    open a bufferlist
    """
    def __init__(self,filtfun=None,**kwargs):
        self.filtfun = filtfun
        Command.__init__(self,**kwargs)
    def apply(self,ui):
        b = buffer.BufferListBuffer(ui,self.filtfun)
        ui.buffers.append(b)
        b.refresh()
        ui.buffer_focus(b)

commands =  {
        'buffer_close': (BufferCloseCommand,{}),
        'buffer_list': (BufferListCommand,{}),
        'buffer_focus': (BufferFocusCommand,{}),
        'buffer_next': (BufferFocusCommand,{'offset': 1}),
        'buffer_prev': (BufferFocusCommand,{'offset': -1}),
        'open_inbox': (SearchCommand,{'query':'tag:inbox'}),
        'open_unread': (SearchCommand,{'query':'tag:unread'}),
        'open_search': (SearchPromptCommand,{}),
        'search': (SearchCommand,{}),
        'shutdown': (ShutdownCommand,{}),
        'shell': (OpenPythonShellCommand,{}),
        'editlog': (EditCommand,{}),
        }

def factory(cmdname,**kwargs):
    if commands.has_key(cmdname):
        cmdclass,parms = commands[cmdname]
        parms=parms.copy()
        parms.update(kwargs)
        for key, value in kwargs.items():
            if callable(value):
                try:
                    parms[key] = value()
                except:
                    parms[key] = None
            else:
                parms[key] = value

        prehook = hooks.get_hook('pre-' +cmdname)
        if prehook:
            parms['prehook'] = prehook
        posthook = hooks.get_hook('post-' +cmdname)
        if posthook:
            parms['posthook'] = hooks.get_hook('post-' +cmdname)
        return cmdclass(**parms)
    else:
        logging.error('there is no command %s'%cmdname)
