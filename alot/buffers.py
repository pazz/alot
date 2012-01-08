import urwid
from notmuch.globals import NotmuchError

import widgets
import settings
import commands
from walker import PipeWalker
from helper import shorten_author_string
from db import NonexistantObjectError


class Buffer(object):
    """Abstract base class for buffers."""
    def __init__(self, ui, widget, name):
        self.ui = ui
        self.typename = name
        self.body = widget

    def __str__(self):
        return '[%s]' % self.typename

    def render(self, size, focus=False):
        return self.body.render(size, focus)

    def selectable(self):
        return self.body.selectable()

    def rebuild(self):
        """tells the buffer to (re)construct its visible content."""
        pass

    def keypress(self, size, key):
            return self.body.keypress(size, key)

    def cleanup(self):
        """called before buffer is dismissed"""
        pass


class BufferlistBuffer(Buffer):
    """selectable list of active buffers"""
    def __init__(self, ui, filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'bufferlist')

    def index_of(self, b):
        """
        returns the index of :class:`Buffer` `b` in the global list of active
        buffers.
        """
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
        """returns currently selected :class:`Buffer` element from list"""
        (linewidget, pos) = self.bufferlist.get_focus()
        bufferlinewidget = linewidget.get_focus().original_widget
        return bufferlinewidget.get_buffer()


class EnvelopeBuffer(Buffer):
    """message composition mode"""
    def __init__(self, ui, envelope):
        self.ui = ui
        self.envelope = envelope
        self.all_headers = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'envelope')

    def __str__(self):
        to = self.envelope.get('To', fallback='unset')
        return '[%s] to: %s' % (self.typename, shorten_author_string(to, 400))

    def rebuild(self):
        displayed_widgets = []
        hidden = settings.config.getstringlist('general',
                                               'envelope_headers_blacklist')
        #build lines
        lines = []
        for (k, vlist) in self.envelope.headers.items():
            if (k not in hidden) or self.all_headers:
                for value in vlist:
                    lines.append((k, value))

        self.header_wgt = widgets.HeadersList(lines)
        displayed_widgets.append(self.header_wgt)

        #display attachments
        lines = []
        for a in self.envelope.attachments:
            lines.append(widgets.AttachmentWidget(a, selectable=False))
        if lines:
            self.attachment_wgt = urwid.Pile(lines)
            displayed_widgets.append(self.attachment_wgt)

        self.body_wgt = urwid.Text(self.envelope.body)
        displayed_widgets.append(self.body_wgt)
        self.body = urwid.ListBox(displayed_widgets)

    def toggle_all_headers(self):
        """toggles visibility of all envelope headers"""
        self.all_headers = not self.all_headers
        self.rebuild()


class SearchBuffer(Buffer):
    """
    shows a result set for a Thread query, one line per
    :class:`~alot.db.Thread`
    """
    threads = []

    def __init__(self, ui, initialquery='', sort_order=None):
        self.dbman = ui.dbman
        self.ui = ui
        self.querystring = initialquery
        default_order = settings.config.get('general',
                                            'search_threads_sort_order')
        self.sort_order = sort_order or default_order
        self.result_count = 0
        self.isinitialized = False
        self.proc = None  # process that fills our pipe
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'search')

    def __str__(self):
        formatstring = '[search] for "%s" (%d thread%s)'
        return formatstring % (self.querystring, self.result_count,
                               's' * (not (self.result_count == 1)))

    def cleanup(self):
        self.kill_filler_process()

    def kill_filler_process(self):
        """
        terminates the process that fills this buffers
        :class:`~alot.walker.PipeWalker`.
        """
        if self.proc:
            if self.proc.is_alive():
                self.proc.terminate()

    def rebuild(self):
        if self.isinitialized:
            pass
            #focusposition = self.threadlist.get_focus()[1]
        else:
            #focusposition = 0
            self.isinitialized = True

        self.kill_filler_process()

        self.result_count = self.dbman.count_messages(self.querystring)
        try:
            self.pipe, self.proc = self.dbman.get_threads(self.querystring,
                                                          self.sort_order)
        except NotmuchError:
            self.ui.notify('malformed query string: %s' % self.querystring,
                           'error')
            self.listbox = urwid.ListBox(self.threadlist)
            self.body = self.listbox
            return

        self.threadlist = PipeWalker(self.pipe, widgets.ThreadlineWidget,
                                     dbman=self.dbman)

        self.listbox = urwid.ListBox(self.threadlist)
        #self.threadlist.set_focus(focusposition)
        self.body = self.listbox

    def get_selected_threadline(self):
        """
        returns curently focussed :class:`alot.widgets.ThreadlineWidget`
        from the result list.
        """
        (threadlinewidget, size) = self.threadlist.get_focus()
        return threadlinewidget

    def get_selected_thread(self):
        """returns currently selected :class:`~alot.db.Thread`"""
        threadlinewidget = self.get_selected_threadline()
        thread = None
        if threadlinewidget:
            thread = threadlinewidget.get_thread()
        return thread


class ThreadBuffer(Buffer):
    """shows a single mailthread as a (collapsible) tree of
    :class:`MessageWidgets <alot.widgets.MessageWidget>`."""
    def __init__(self, ui, thread):
        self.message_count = thread.get_total_messages()
        self.thread = thread
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'thread')

    def __str__(self):
        return '[thread] %s (%d message%s)' % (self.thread.get_subject(),
                                               self.message_count,
                                               's' * (self.message_count > 1))

    def get_selected_thread(self):
        """returns the displayed :class:`~alot.db.Thread`"""
        return self.thread

    def _build_pile(self, acc, msg, parent, depth):
        acc.append((parent, depth, msg))
        for reply in self.thread.get_replies_to(msg):
            self._build_pile(acc, reply, msg, depth + 1)

    def rebuild(self):
        try:
            self.thread.refresh()
        except NonexistantObjectError:
            self.body = urwid.SolidFill()
            self.message_count = 0
            return
        # depth-first traversing the thread-tree, thereby
        # 1) build a list of tuples (parentmsg, depth, message) in DF order
        # 2) create a dict that counts no. of direct replies per message
        messages = list()  # accumulator for 1,
        childcount = {None: 0}  # accumulator for 2)
        for msg, replies in self.thread.get_messages().items():
            childcount[msg] = len(replies)
        # start with all toplevel msgs, then recursively call _build_pile
        for msg in self.thread.get_toplevel_messages():
            self._build_pile(messages, msg, None, 0)
            childcount[None] += 1

        # go through list from 1) and pile up message widgets for all msgs.
        # each one will be given its depth, if siblings follow and where to
        # draw bars (siblings follow at lower depths)
        msglines = list()
        bars = []
        for (num, (p, depth, m)) in enumerate(messages):
            bars = bars[:depth]
            childcount[p] -= 1

            bars.append(childcount[p] > 0)
            mwidget = widgets.MessageWidget(m, even=(num % 2 == 0),
                                            depth=depth,
                                            bars_at=bars)
            msglines.append(mwidget)

        self.body = urwid.ListBox(msglines)
        self.message_count = self.thread.get_total_messages()

    def get_selection(self):
        """returns focussed :class:`~alot.widgets.MessageWidget`"""
        (messagewidget, size) = self.body.get_focus()
        return messagewidget

    def get_messagewidgets(self):
        """returns all message widgets contained in this list"""
        return self.body.body.contents

    def get_selected_message(self):
        """returns focussed :class:`~alot.message.Message`"""
        messagewidget = self.get_selection()
        return messagewidget.get_message()

    def get_message_widgets(self):
        """
        returns all :class:`MessageWidgets <alot.widgets.MessageWidget>`
        displayed in this thread-tree.
        """
        return self.body.body.contents

    def get_focus(self):
        return self.body.get_focus()

    def unfold_matching(self, querystring):
        """
        unfolds those :class:`MessageWidgets <alot.widgets.MessageWidget>`
        that represent :class:`Messages <alot.message.Message>` matching
        `querystring`.
        """
        for mw in self.get_message_widgets():
            msg = mw.get_message()
            if msg.matches(querystring):
                mw.folded = False
                if 'unread' in msg.get_tags():
                    msg.remove_tags(['unread'])
                    self.ui.apply_command(commands.globals.FlushCommand())
                mw.rebuild()


class TagListBuffer(Buffer):
    """selectable list of tagstrings present in the database"""
    def __init__(self, ui, alltags=[], filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        self.tags = alltags
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'taglist')

    def rebuild(self):
        if self.isinitialized:
            focusposition = self.taglist.get_focus()[1]
        else:
            focusposition = 0
            self.isinitialized = True

        lines = list()
        displayedtags = sorted(filter(self.filtfun, self.tags),
                               key=unicode.lower)
        for (num, b) in enumerate(displayedtags):
            tw = widgets.TagWidget(b)
            lines.append(urwid.Columns([('fixed', tw.width(), tw)]))
        self.taglist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.body = self.taglist

        self.taglist.set_focus(focusposition % len(displayedtags))

    def get_selected_tag(self):
        """returns selected tagstring"""
        (cols, pos) = self.taglist.get_focus()
        tagwidget = cols.get_focus()
        return tagwidget.get_tag()
