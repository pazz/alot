import urwid

import settings
from ng import command
from ng.widgets import PromptWidget


class UI:
    buffers = []
    current_buffer = None

    def __init__(self, db, log, **args):
        self.logger = log
        self.dbman = db

        self.logger.error(args)
        self.logger.debug('setup gui')
        self.mainframe = urwid.Frame(urwid.SolidFill(' '))
        self.mainloop = urwid.MainLoop(self.mainframe,
                settings.palette,
                handle_mouse=args['handle_mouse'],
                unhandled_input=self.keypress)
        #self.mainloop.screen.set_terminal_properties(colors=256)
        self.mainloop.screen.set_terminal_properties(colors=16)

        self.logger.debug('setup bindings')
        self.bindings = {
            'i': ('open_inbox', {}),
            'u': ('open_unread', {}),
            'x': ('buffer_close', {}),
            'tab': ('buffer_next', {}),
            'shift tab': ('buffer_prev', {}),
            '\\': ('open_search', {}),
            'q': ('shutdown', {}),
            ';': ('buffer_list', {}),
            's': ('shell', {}),
            'v': ('view_log', {}),
        }

        cmd = command.factory('open_inbox')
        self.apply_command(cmd)
        self.mainloop.run()

    def shutdown(self):
        """
        close the ui. this is _not_ the main shutdown procedure:
        there is a shutdown command that will eventually call this.
        """
        raise urwid.ExitMainLoop()

    def prompt(self, prefix):
        self.logger.info('open prompt')

        p = PromptWidget(prefix)
        footer = self.mainframe.get_footer()
        self.mainframe.set_footer(p)
        self.mainframe.set_focus('footer')
        self.mainloop.draw_screen()
        while True:
            keys = None
            while not keys:
                keys = self.mainloop.screen.get_input()
            for k in keys:
                if k == 'enter':
                    self.mainframe.set_footer(footer)
                    self.mainframe.set_focus('body')
                    return p.get_input()
                if k in ('escape', 'tab'):
                    self.mainframe.set_footer(footer)
                    self.mainframe.set_focus('body')
                    return None
                else:
                    size = (20,)  # don't know why they want a size here
                    p.editpart.keypress(size, k)
                    self.mainloop.draw_screen()

    def buffer_open(self, b):
        """
        register and focus new buffer
        """
        self.buffers.append(b)
        self.buffer_focus(b)

    def buffer_close(self, b):
        buffers = self.buffers
        if b not in buffers:
            string = 'tried to close unknown buffer: %s. \n\ni have:%s'
            self.logger.error(string % (b, self.buffers))
        elif len(buffers) == 1:
            self.logger.info('closing the last buffer, exiting')
            cmd = command.factory('shutdown')
            self.apply_command(cmd)
        else:
            if self.current_buffer == b:
                self.logger.debug('UI: closing current buffer %s' % b)
                index = buffers.index(b)
                buffers.remove(b)
                self.current_buffer = buffers[index % len(buffers)]
            else:
                string = 'closing buffer %d:%s'
                self.logger.debug(string % (buffers.index(b), b))
                index = buffers.index(b)
                buffers.remove(b)

    def buffer_focus(self, b):
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
        #who needs a header?
        #head = urwid.Text('notmuch gui')
        #h=urwid.AttrMap(head, 'header')
        #self.mainframe.set_header(h)

        #body
        self.mainframe.set_body(self.current_buffer)

        #footer
        self.update_footer()

    def update_footer(self):
        i = self.buffers.index(self.current_buffer)
        lefttxt = '%d: %s' % (i, self.current_buffer)
        footerleft = urwid.Text(lefttxt, align='left')
        righttxt = 'total messages: %d' % self.dbman.count_messages('*')
        footerright = urwid.Text(righttxt, align='right')
        columns = urwid.Columns([
            footerleft,
            ('fixed', len(righttxt), footerright)])
        footer = urwid.AttrMap(columns, 'footer')
        self.mainframe.set_footer(footer)

    def keypress(self, key):
        if self.bindings.has_key(key):
            self.logger.debug("got globally bounded key: %s" % key)
            (cmdname, parms) = self.bindings[key]
            cmd = command.factory(cmdname, **parms)
            self.apply_command(cmd)
        else:
            self.logger.debug('unhandeled input: %s' % input)

    def apply_command(self, cmd):
        if cmd:
            if cmd.prehook:
                self.logger.debug('calling pre-hook')
                try:
                    cmd.prehook(self)
                except:
                    self.logger.error('prehook failed')
                    raise
            self.logger.debug('apply command: %s' % cmd)
            cmd.apply(self)
            if cmd.posthook:
                self.logger.debug('calling post-hook')
                try:
                    cmd.posthook(self)
                except:
                    self.logger.error('posthook failed')
                    raise
