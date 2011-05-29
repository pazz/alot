import urwid

import widgets
import command
from walker import IteratorWalker


class Buffer:
    def __init__(self, ui, widget, name):
        self.ui = ui
        self.typename = name
        self.bindings = {}
        self._autoparms = {}
        self.body = widget

    def __str__(self):
        return ''

    def render(self, size, focus=False):
        return self.body.render(size, focus)

    def selectable(self):
        return self.body.selectable()

    def rebuild(self):
        pass

    def apply_command(self, cmd):
        # call and store it directly for a local cmd history
        self.ui.apply_command(cmd)

    def keypress(self, size, key):
        if key in self.bindings:
            self.ui.logger.debug("%s: handles key: %s" % (self.typename, key))
            (cmdname, parms) = self.bindings[key]
            parms = parms.copy()
            parms.update(self._autoparms)
            try:
                cmd = command.factory(cmdname, **parms)
                self.apply_command(cmd)
            except AssertionError as e:
                string = "could not instanciate command %s(%s): %s"
                self.ui.logger.exception(string % (cmdname, parms))
        else:
            if key == 'j':
                key = 'down'
            elif key == 'k':
                key = 'up'
            elif key == ' ':
                key = 'page down'
            elif key == 'r':
                self.rebuild()
            return self.body.keypress(size, key)


class BufferListBuffer(Buffer):
    def __init__(self, ui, filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'bufferlist')
        self._autoparms = {'buffer': self.get_selected_buffer}
        self.bindings = {
            'd': ('buffer_close', {}),
            'enter': ('buffer_focus', {}),
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
            if (num % 2) == 0:
                attr = 'bufferlist_results_even'
            else:
                attr = 'bufferlist_results_odd'
            buf = urwid.AttrMap(line, attr, 'bufferlist_focus')
            num = urwid.Text('%3d:' % self.index_of(b))
            lines.append(urwid.Columns([('fixed', 4, num), buf]))
        self.bufferlist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.bufferlist.set_focus(focusposition % len(displayedbuffers))
        self.body = self.bufferlist

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
        Buffer.__init__(self, ui, self.body, 'search')
        self._autoparms = {'thread': self.get_selected_thread}
        self.bindings = {
            'enter': ('open_thread', {}),
            'l': ('thread_tag_prompt', {}),
            '|': ('refine_search_prompt', {}),
            'a': ('toggle_thread_tag', {'tag': 'inbox'}),
            '&': ('toggle_thread_tag', {'tag': 'killed'}),
        }

    def __str__(self):
        return '%s (%d threads)' % (self.querystring, self.result_count)

    def rebuild(self):
        if self.isinitialized:
            focusposition = self.threadlist.get_focus()[1]
        else:
            focusposition = 0
            self.isinitialized = True

        self.result_count = self.dbman.count_messages(self.querystring)
        self.tids = self.dbman.search_thread_ids(self.querystring)
        self.threadlist = IteratorWalker(iter(self.tids),
                                         widgets.ThreadlineWidget,
                                         dbman=self.dbman)
        self.listbox = urwid.ListBox(self.threadlist)
        self.body = self.listbox

    def debug(self):
        self.ui.logger.debug(self.threadlist.lines)

    def get_selected_threadline(self):
        (threadlinewidget, size) = self.threadlist.get_focus()
        return threadlinewidget

    def get_selected_thread(self):
        threadlinewidget = self.get_selected_threadline()
        thread = None
        if threadlinewidget:
            thread = threadlinewidget.get_thread()
        return thread


class SingleThreadBuffer(Buffer):
    def __init__(self, ui, thread):
        self.message_count = thread.get_total_messages()
        self.subject = thread.get_subject()
        self.messages = [(0, m) for m in thread.get_toplevel_messages()]
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'thread')
        self.bindings = {}

    def __str__(self):
        return '%s, (%d)' % (self.thread.subject, self.message_count)

    def rebuild(self):
        msgs = list()
        for (num, (depth, m)) in enumerate(self.messages, 1):
            mwidget = widgets.MessageWidget(m, even=(num % 2 == 0),
                                            folded=False)
            # a spacer of width 0 breaks urwid.Columns
            if depth == 0:
                msgs.append(urwid.Columns([mwidget]))
            else:
                spacer = urwid.Text(' ' * depth)
                msgs.append(urwid.Columns([('fixed', depth, spacer), mwidget]))
        self.body = urwid.ListBox(msgs)

    def get_selected_message(self):
        (messagewidget, size) = self.body.get_focus()
        return messagewidget.get_message()


class TagListBuffer(Buffer):
    def __init__(self, ui, alltags=[], filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        self.tags = alltags
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'taglist')
        self._autoparms = {}
        self.bindings = {
            'enter': ('search', {'query': (lambda: 'tag:' +
                                           self.get_selected_tag())}),
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
        self.body = self.taglist

        self.taglist.set_focus(focusposition % len(displayedtags))

    def get_selected_tag(self):
        (attrwidget, pos) = self.taglist.get_focus()
        tagwidget = attrwidget.original_widget
        return str(tagwidget.get_tag())
