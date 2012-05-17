import urwid
from notmuch import NotmuchError

import widgets
from settings import settings
import commands
from walker import PipeWalker
from helper import shorten_author_string
from db.errors import NonexistantObjectError


class Buffer(object):
    """Abstract base class for buffers."""

    modename = None  # mode identifier for subclasses

    def __init__(self, ui, widget):
        self.ui = ui
        self.body = widget

    def __str__(self):
        return '[%s]' % self.modename

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
    """lists all active buffers"""

    modename = 'bufferlist'

    def __init__(self, ui, filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

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
                attr = settings.get_theming_attribute('bufferlist',
                                                      'results_even')
            else:
                attr = settings.get_theming_attribute('bufferlist',
                                                      'results_odd')
            focus_att = settings.get_theming_attribute('bufferlist', 'focus')
            buf = urwid.AttrMap(line, attr, focus_att)
            num = urwid.Text('%3d:' % self.index_of(b))
            lines.append(urwid.Columns([('fixed', 4, num), buf]))
        self.bufferlist = urwid.ListBox(urwid.SimpleListWalker(lines))
        num_buffers = len(displayedbuffers)
        if focusposition is not None and num_buffers > 0:
            self.bufferlist.set_focus(focusposition % num_buffers)
        self.body = self.bufferlist

    def get_selected_buffer(self):
        """returns currently selected :class:`Buffer` element from list"""
        (linewidget, pos) = self.bufferlist.get_focus()
        bufferlinewidget = linewidget.get_focus().original_widget
        return bufferlinewidget.get_buffer()


class EnvelopeBuffer(Buffer):
    """message composition mode"""

    modename = 'envelope'

    def __init__(self, ui, envelope):
        self.ui = ui
        self.envelope = envelope
        self.all_headers = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

    def __str__(self):
        to = self.envelope.get('To', fallback='unset')
        return '[envelope] to: %s' % (shorten_author_string(to, 400))

    def rebuild(self):
        displayed_widgets = []
        hidden = settings.get('envelope_headers_blacklist')
        #build lines
        lines = []
        for (k, vlist) in self.envelope.headers.items():
            if (k not in hidden) or self.all_headers:
                for value in vlist:
                    lines.append((k, value))

        # sign/encrypt lines
        if self.envelope.sign:
            description = 'Yes'
            sign_key = self.envelope.sign_key
            if sign_key is not None and len(sign_key.subkeys) > 0:
                description += ', with key ' + sign_key.subkeys[0].keyid
            lines.append(('GPG sign', description))

        # add header list widget iff header values exists
        if lines:
            key_att = settings.get_theming_attribute('envelope', 'header_key')
            value_att = settings.get_theming_attribute('envelope', 'header_value')
            self.header_wgt = widgets.HeadersList(lines, key_att, value_att)
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
    """shows a result list of threads for a query"""

    modename = 'search'
    threads = []

    def __init__(self, ui, initialquery='', sort_order=None):
        self.dbman = ui.dbman
        self.ui = ui
        self.querystring = initialquery
        default_order = settings.get('search_threads_sort_order')
        self.sort_order = sort_order or default_order
        self.result_count = 0
        self.isinitialized = False
        self.proc = None  # process that fills our pipe
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

    def __str__(self):
        formatstring = '[search] for "%s" (%d message%s)'
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
    """displays a thread as a tree of messages"""

    modename = 'thread'

    def __init__(self, ui, thread):
        self.message_count = thread.get_total_messages()
        self.thread = thread
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

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
        """returns focussed :class:`~alot.db.message.Message`"""
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
        that represent :class:`Messages <alot.db.message.Message>` matching
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
    """lists all tagstrings present in the notmuch database"""

    modename = 'taglist'

    def __init__(self, ui, alltags=[], filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        self.tags = alltags
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

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
            rows = [('fixed', tw.width(), tw)]
            if tw.hidden:
                rows.append(urwid.Text('[hidden]'))
            elif tw.translated is not b:
                rows.append(urwid.Text('(%s)' % b))
            lines.append(urwid.Columns(rows, dividechars=1))
        self.taglist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.body = self.taglist

        self.taglist.set_focus(focusposition % len(displayedtags))

    def get_selected_tag(self):
        """returns selected tagstring"""
        (cols, pos) = self.taglist.get_focus()
        tagwidget = cols.get_focus()
        return tagwidget.get_tag()
