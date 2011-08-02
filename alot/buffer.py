"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
import urwid

import widgets
import settings
from walker import IteratorWalker
from message import decode_header


class Buffer:
    def __init__(self, ui, widget, name):
        self.ui = ui
        self.typename = name
        self.autoparms = {}
        self.body = widget

    def __str__(self):
        return self.typename

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
            return self.body.keypress(size, key)


class BufferlistBuffer(Buffer):
    def __init__(self, ui, filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'bufferlist')
        self.autoparms = {'buffer': self.get_selected_buffer}

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


class EnvelopeBuffer(Buffer):
    def __init__(self, ui, mail):
        self.ui = ui
        self.mail = mail
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'envelope')
        self.autoparms = {'email': self.get_email}

    def __str__(self):
        return "to: %s" % decode_header(self.mail['To'])

    def get_email(self):
        return self.mail

    def set_email(self, mail):
        self.mail = mail
        self.rebuild()

    def rebuild(self):
        displayed_widgets = []
        dh = settings.config.getstringlist('general', 'displayed_headers')
        self.header_wgt = widgets.MessageHeaderWidget(self.mail,
                                                      displayed_headers=dh)
        displayed_widgets.append(self.header_wgt)
        self.body_wgt = widgets.MessageBodyWidget(self.mail)
        displayed_widgets.append(self.body_wgt)
        self.body = urwid.ListBox(displayed_widgets)


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
        self.autoparms = {'thread': self.get_selected_thread}

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
        #self.threadlist.set_focus(focusposition)
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


class ThreadBuffer(Buffer):
    def __init__(self, ui, thread):
        self.message_count = thread.get_total_messages()
        self.thread = thread
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'thread')
        self.autoparms = {'thread': self.thread}

    def __str__(self):
        return '%s, (%d)' % (self.thread.get_subject(), self.message_count)

    def get_selected_thread(self):
        return self.thread

    def _build_pile(self, acc, msg, parent, depth):
        acc.append((parent, depth, msg))
        for reply in self.thread.get_replies_to(msg):
            self._build_pile(acc, reply, msg, depth + 1)

    def rebuild(self):
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
                                            unfold_header=False,  # settings
                                            unfold_body=False,
                                            depth=depth,
                                            bars_at=bars)
            msglines.append(mwidget)
        self.body = urwid.ListBox(msglines)

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
        self.autoparms = {}

    def rebuild(self):
        if self.isinitialized:
            focusposition = self.taglist.get_focus()[1]
        else:
            focusposition = 0
            self.isinitialized = True

        lines = list()
        displayedtags = filter(self.filtfun, self.tags)
        for (num, b) in enumerate(displayedtags):
            tw = widgets.TagWidget(b)
            lines.append(urwid.Columns([('fixed', tw.len(), tw)]))
        self.taglist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.body = self.taglist

        self.taglist.set_focus(focusposition % len(displayedtags))

    def get_selected_tag(self):
        (cols, pos) = self.taglist.get_focus()
        tagwidget = cols.get_focus()
        return tagwidget.get_tag()
