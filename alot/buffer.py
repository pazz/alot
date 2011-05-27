import urwid

import widgets
import command
from walker import IteratorWalker


class Buffer(urwid.AttrMap):
    def __init__(self, ui, widget, name):
        self.ui = ui
        self.typename = name
        self.bindings = {}
        urwid.AttrMap.__init__(self, widget, {})

    def rebuild(self):
        pass

    def __str__(self):
        return "[%s]" % (self.typename)

    def apply_command(self, cmd):
        #call and store it directly for a local cmd history
        self.ui.apply_command(cmd)
        #self.rebuild()

    def keypress(self, size, key):
        if key in self.bindings:
            self.ui.logger.debug("%s: handeles key: %s" % (self.typename, key))
            (cmdname, parms) = self.bindings[key]
            cmd = command.factory(cmdname, **parms)
            self.apply_command(cmd)
        else:
            if key == 'j': key = 'down'
            elif key == 'k': key = 'up'
            elif key == 'h': key = 'left'
            elif key == 'l': key = 'right'
            elif key == ' ': key = 'page down'
            elif key == 'r': self.rebuild()
            elif key == 't': self.debug()
            return self.original_widget.keypress(size, key)


class BufferListBuffer(Buffer):
    def __init__(self, ui, filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.original_widget, 'bufferlist')
        self.bindings = {
                         'd': ('buffer_close',
                               {'buffer': self.get_selected_buffer}),
                         'enter': ('buffer_focus',
                                   {'buffer': self.get_selected_buffer}),
                         }

    def index_of(self, b):
        return self.ui.buffers.index(b)

    def rebuild(self):
        if self.isinitialized:
            focusposition = self.bufferlist.get_focus()[1]
        else:
            focusposition = 0
            self.isinitialized = True

        lines = list()
        displayedbuffers = filter(self.filtfun, self.ui.buffers)
        for (num, b) in enumerate(displayedbuffers):
            line = widgets.BufferlineWidget(b)
            if (num % 2) == 0: attr = 'bufferlist_results_even'
            else: attr = 'bufferlist_results_odd'
            buf = urwid.AttrMap(line, attr, 'bufferlist_focus')
            num = urwid.Text('%3d:' % self.index_of(b))
            lines.append(urwid.Columns([('fixed', 4, num), buf]))
        self.bufferlist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.original_widget = self.bufferlist

        self.bufferlist.set_focus(focusposition%len(displayedbuffers))

    def get_selected_buffer(self):
        (linewidget, pos) = self.bufferlist.get_focus()
        bufferlinewidget = linewidget.get_focus().original_widget
        return bufferlinewidget.get_buffer()


class SearchBuffer(Buffer):
    threads = []

    def __init__(self, ui, initialquery=''):
        self.dbman = ui.dbman
        self.ui = ui
        self.querystring = initialquery
        self.result_count = 0
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.original_widget, 'search')
        self.ui.logger.info("\n\n"+self.typename)
        self.bindings = {
                'enter': ('open_thread', {'thread': self.get_selected_thread}),
                'a': ('toggle_thread_tag', {'thread': self.get_selected_thread,
                                            'tag': 'inbox'}),
                }

    def rebuild(self):
        if self.isinitialized:
            focusposition = self.threadlist.get_focus()[1]
        else:
            focusposition = 0
            self.isinitialized = True

        self.result_count = self.dbman.count_messages(self.querystring)
        self.tids = self.dbman.search_thread_ids(self.querystring)
        self.threadlist = IteratorWalker(self.tids.__iter__(), widgets.ThreadlineWidget,
                                         dbman=self.dbman)
        self.ui.logger.debug(len(self.tids))
        self.original_widget = urwid.ListBox(self.threadlist)
        self.ui.logger.debug(self.threadlist.lines)

        self.threadlist.set_focus(focusposition)

    def debug(self):
        self.ui.logger.debug(self.threadlist.lines)

    def __str__(self):
        string = "[%s] for %s, (%d)"
        return string % (self.typename, self.querystring, self.result_count)

    def get_selected_threadline(self):
        (threadlinewidget, size) = self.threadlist.get_focus()
        return threadlinewidget

    def get_selected_thread(self):
        threadlinewidget = self.get_selected_threadline()
        return threadlinewidget.get_thread()


class SingleThreadBuffer(Buffer):
    def __init__(self, ui, thread):
        self.read_thread(thread)
        self.rebuild()
        Buffer.__init__(self, ui, self.original_widget, 'search')
        self.bindings = {
                         'enter': ('call_pager',
                                   {'path': self.get_selected_message_file}),
                         }

    def read_thread(self, thread):
        self.message_count = thread.get_total_messages()
        self.subject = thread.get_subject()
        # list() throws an error
        self.messages = [m for m in thread.get_toplevel_messages()]

    def rebuild(self):
        msgs = list()
        for (num, m) in enumerate(self.messages, 1):
            msgs.append(widgets.MessageWidget(m, even=(num % 2 == 0)))
        self.messagelist = urwid.ListBox(msgs)
        self.original_widget = self.messagelist

    def __str__(self):
        string = "[%s] %s, (%d)"
        return string % (self.typename, self.subject, self.message_count)

    def get_selected_message(self):
        (messagewidget, size) = self.messagelist.get_focus()
        return messagewidget.get_message()

    def get_selected_message_file(self):
        return self.get_selected_message().get_filename()


class TagListBuffer(Buffer):
    def __init__(self, ui, alltags=[], filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        self.tags = alltags
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.original_widget, 'taglist')
        self.bindings = {'enter': ('search',
                                   {'query': self.get_selected_tag}),
                         }

    def rebuild(self):
        if self.isinitialized:
            focusposition = self.taglist.get_focus()[1]
        else:
            focusposition = 0
            self.isinitialized = True

        lines = list()
        displayedtags = filter(self.filtfun, self.tags)
        for (num, b) in enumerate(displayedtags):
            line = widgets.TagWidget(b)
            tag_w = urwid.AttrMap(line, 'taglist_tag', 'taglist_focus')
            lines.append(tag_w)
        self.taglist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.original_widget = self.taglist

        self.taglist.set_focus(focusposition%len(displayedtags))

    def get_selected_tag(self):
        (attrwidget, pos) = self.taglist.get_focus()
        tagwidget = attrwidget.original_widget
        return 'tag:'+tagwidget.get_tag()
