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
            '\\': ('open_search',{}),
            'q': ('shutdown',{}),
            ';': ('buffer_list',{}),
            's': ('shell',{}),
            'v': ('editlog',{}),
        }

        cmd = command.factory('open_unread')
        self.apply_command(cmd)
        self.mainloop.run()

    def shutdown(self):
        """
        close the ui. this is _not_ the main shutdown procedure:
        there is a shutdown command that will eventually call this.
        """
        raise urwid.ExitMainLoop()

    def prompt(self, prefix):
        self.logger.info('PROMPT')

        def restore():
            self.mainframe.set_focus('body')
            self.update_footer()

        p = widgets.PromptWidget(prefix)
        self.mainframe.set_footer(p)
        #set body unfocussable
        self.mainframe.set_focus('footer')

        keypress = self.keypress
        def restore():
            self.keypress = keypress
            self.mainframe.set_focus('body')
            self.update_footer()
        def keypress_during_prompt(self, size, key):
            if key=='enter':
                result = p.get_input()
                self.logger.info('enter: %s'%result)
                restore()
                yield result
            elif key in ['escape','tab']:
                self.logger.info('cancel')
                restore()
                yield None
            else:
                yield p.keypress(size,key)
        self.keypress = keypress_during_prompt

    def buffer_open(self,b):
        """
        register and focus new buffer
        """

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
        """
        focus given buffer. must be contained in self.buffers
        """
        if b not in self.buffers:
            self.logger.error('tried to focus unknown buffer')
        else:
            self.current_buffer = b
            self.current_buffer.refresh()
            self.update()

    def update(self):
        """
        redraw interface
        """
        #header
        head = urwid.Text('notmuch gui')
        h=urwid.AttrMap(head, 'header')

        #body
        self.mainframe.set_header(h)
        self.mainframe.set_body(self.current_buffer)

        #footer
        self.update_footer()

    def update_footer(self):
        i = self.buffers.index(self.current_buffer)
        lefttxt = '%d: %s'%(i,self.current_buffer)
        footerleft = urwid.Text(lefttxt,align='left')
        righttxt = 'total messages: %d'%self.dbman.count_messages('*')
        footerright = urwid.Text(righttxt,align='right')
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
