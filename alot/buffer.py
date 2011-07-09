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
import command
from walker import IteratorWalker
from itertools import izip_longest


class Buffer:
    def __init__(self, ui, widget, name):
        self.ui = ui
        self.typename = name
        self.bindings = {}
        self._autoparms = {}
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
        if key in self.bindings:
            self.ui.logger.debug("%s: handles key: %s" % (self.typename, key))
            (cmdname, parms) = self.bindings[key]
            parms = parms.copy()
            parms.update(self._autoparms)
            try:
                cmd = command.factory(cmdname, **parms)
                self.apply_command(cmd)
            except AssertionError as e:
                string = "could not instanciate command %s with params %s"
                self.ui.logger.debug(string % (cmdname, parms.items()))
        else:
            #if key == 'j':
            #    key = 'down'
            #elif key == 'k':
            #    key = 'up'
            #elif key == ' ':
            #    key = 'page down'
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


class SingleThreadBuffer(Buffer):
    def __init__(self, ui, thread):
        self.message_count = thread.get_total_messages()
        self.thread = thread
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'thread')
        self._autoparms = {'thread': self.thread}
        self.bindings = {
            'a': ('toggle_thread_tag', {'tag': 'inbox'}),
        }

    def __str__(self):
        return '%s, (%d)' % (self.thread.get_subject(), self.message_count)

    def _build_pile(self, acc, childcount, msg, replies, parent, depth=0):
        acc.append((parent, depth, msg))
        childcount[parent] += 1
        for (reply, rereplies) in replies.items():
            if reply not in childcount:
                childcount[reply] = 0
            self._build_pile(acc, childcount, reply, rereplies, msg, depth + 1)

    def rebuild(self):
        # depth-first traversing the thread-tree, thereby
        # 1) build a list of tuples (parentmsg, depth, message) in DF order
        # 2) create a dict that counts no. of direct replies per message
        messages = list()  # accumulator for 1,
        childcount = {None: 0}  # accumulator for 2)
        # start with all toplevel msgs, then recursively call _build_pile
        for (msg, replies) in self.thread.get_message_tree().items():
            if msg not in childcount:  # in create entry for current msg
                childcount[msg] = 0
            self._build_pile(messages, childcount, msg, replies, None)

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
        return tagwidget.get_tag()


class EnvelopeBuffer(Buffer):
    def __init__(self, ui, email):
        self.ui = ui
        self.email = email
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'envelope')
        self._autoparms = {'email': self.get_email}
        self.bindings = {
            'y': ('send', {'envelope': self}),
        }

    def get_email(self):
        return self.email

    def rebuild(self):
        displayed_widgets = []
        self.header_wgt = widgets.MessageHeaderWidget(self.email)
        displayed_widgets.append(self.header_wgt)
        self.body_wgt = widgets.MessageBodyWidget(self.email)
        displayed_widgets.append(self.body_wgt)
        self.body = urwid.ListBox(displayed_widgets)
