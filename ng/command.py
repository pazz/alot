import urwid
import logging
import buffer
import hooks

class Command:
    def __init__(self,prehook=None,posthook=None):
        self.prehook = prehook
        self.posthook = posthook
        self.undoable = False
    def apply(self,caller):
        return

class ShutdownCommand(Command):
    def apply(self,ui):
        ui.shutdown()

class SearchCommand(Command):
    def __init__(self,query=None,**kwargs):
        self.query = query
        Command.__init__(self,**kwargs)
    def apply(self,ui):
        #get query fron input?
        if not self.query:
            self.query='*'
        sb = buffer.SearchBuffer(ui,self.query)
        ui.buffer_open(sb)

class EditCommand(Command):
    def apply(self,ui):
        #TODO tell screen to echo input!
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
    def apply(self,ui):
        import code
        ui.mainloop.screen.stop()
        code.interact(local=locals())
        ui.mainloop.screen.start()

class BufferCloseCommand(Command):
    def __init__(self,buffer=None,**kwargs):
        self.buffer = buffer
        Command.__init__(self,**kwargs)
    def apply(self,ui):
        if not self.buffer:
            self.buffer=ui.current_buffer
        ui.buffer_close(self.buffer)
        ui.buffer_focus(ui.current_buffer)

class BufferFocusCommand(Command):
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
        'search': (SearchCommand,{}),
        'shutdown': (ShutdownCommand,{}),
        'shell': (OpenPythonShellCommand,{}),
        'editlog': (EditCommand,{}),
        }

def factory(cmdname,**kwargs):
    if commands.has_key(cmdname):
        cmdclass,parms = commands[cmdname]
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
