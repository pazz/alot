import urwid
import settings
from ng.buffer import *
from ng import command

class UI:
    buffers = []
    current_buffer = None

    def __init__(self,db,log,**args):
        self.logger = log
        self.dbman = db

        self.logger.debug('setup gui')
        self.mainframe = urwid.Frame(urwid.SolidFill(' '))
        self.mainloop = urwid.MainLoop(self.mainframe, settings.palette,
                unhandled_input=self.keypress)
        #self.mainloop.screen.set_terminal_properties(colors=256)
        self.mainloop.screen.set_terminal_properties(colors=16)

        self.logger.debug('setup bindings')
        self.bindings = {
            'i': ('open_inbox',{}),
            'u': ('open_unread',{}),
            'x': ('buffer_close',{}),
            'tab': ('buffer_next',{}),
            'shift tab': ('buffer_prev',{}),
            #'\\': ('search',{}),
            'q': ('shutdown',{}),
            ';': ('buffer_list',{}),
            's': ('shell',{}),
            'v': ('editlog',{}),
        }

        cmd = command.factory('open_unread')
        self.apply_command(cmd)
        self.mainloop.run()

    def shutdown(self):
        raise urwid.ExitMainLoop()

    def buffer_open(self,b):
        self.buffers.append(b)
        self.buffer_focus(b)

    def buffer_close(self,b):
        buffers = self.buffers
        self.logger.debug('buffers: %s'%buffers)
        self.logger.debug('current_buffer: %s'%self.current_buffer)
        if b not in buffers:
            self.logger.error('tried to close unknown buffer: %s. \n\ni have:%s'%(b,self.buffers))
        elif len(buffers)==1:
            self.logger.info('closing the last buffer, exiting')
            cmd = command.factory('shutdown')
            self.apply_command(cmd)
        else:
            if self.current_buffer == b:
                self.logger.debug('closing current buffer %s'%b)
                index = buffers.index(b)
                buffers.remove(b)
                self.current_buffer = buffers[index%len(buffers)]
            else:
                self.logger.debug('closing current buffer %d:%s'%(buffers.index(b),b))
                buffers.remove(b)
        self.logger.debug('buffers: %s'%buffers)
        self.logger.debug('current_buffer: %s'%self.current_buffer)

    def buffer_focus(self,b):
        if b not in self.buffers:
            self.logger.error('tried to focus unknown buffer')
        else:
            self.current_buffer = b
            self.current_buffer.refresh()
            self.update()

    def update(self):
        i = self.buffers.index(self.current_buffer)
        head = urwid.Text('notmuch gui')
        h=urwid.AttrMap(head, 'header')
        self.mainframe.set_header(h)
        self.mainframe.set_body(self.current_buffer)
        #self.mainframe.set_body(self.current_buffer.widget)

        footerleft = urwid.Text('%d: %s'%(i,self.current_buffer))
        footerright = urwid.Text('%d total messages'%self.dbman.count_messages('*'))
        footer=urwid.AttrMap(urwid.Columns([footerleft,footerright]), 'footer')
        self.mainframe.set_footer(footer)

    def keypress(self,key):
        if self.bindings.has_key(key):
            logging.debug("got globally bounded key: %s"%key)
            cmdname,parms = self.bindings[key]
            cmd = command.factory(cmdname,**parms)
            self.apply_command(cmd)
        else:
            self.logger.info('unhandeled input: %s'%input)

    def apply_command(self,cmd):
        if cmd:
            if cmd.prehook:
                self.logger.debug('calling pre-hook')
                try:
                    cmd.prehook(self)
                except:
                    self.logger.error('prehook failed')
                    raise
            self.logger.debug('apply command')
            cmd.apply(self)
            if cmd.posthook:
                self.logger.debug('calling post-hook')
                try:
                    cmd.posthook(self)
                except:
                    self.logger.error('posthook failed')
                    raise
