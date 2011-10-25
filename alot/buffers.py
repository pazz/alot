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
from notmuch.globals import NotmuchError
from itertools import imap


import widgets
import settings
import commands
from walker import IteratorWalker
from message import decode_header


class Buffer(object):
    def __init__(self, ui, widget, name):
        self.ui = ui
        self.typename = name
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

    def __str__(self):
        return "to: %s" % decode_header(self.mail['To'])

    def get_email(self):
        return self.mail

    def set_email(self, mail):
        self.mail = mail
        self.rebuild()

    def rebuild(self):
        displayed_widgets = []
        hidden = settings.config.getstringlist('general',
                                               'envelope_headers_blacklist')
        self.header_wgt = widgets.MessageHeaderWidget(self.mail,
                                                      hidden_headers=hidden)
        displayed_widgets.append(self.header_wgt)

        #display attachments
        lines = []
        for part in self.mail.walk():
            if not part.is_multipart():
                if part.get_content_maintype() != 'text':
                    lines.append(widgets.AttachmentWidget(part,
                                                        selectable=False))
        self.attachment_wgt = urwid.Pile(lines)
        displayed_widgets.append(self.attachment_wgt)

        self.body_wgt = widgets.MessageBodyWidget(self.mail)
        displayed_widgets.append(self.body_wgt)
        self.body = urwid.ListBox(displayed_widgets)


class MessagesBuffer(Buffer):
    threads = []

    def __init__(self, ui, query, sort_by='oldest_first'):
        self.dbman = ui.dbman
        self.sort_by = sort_by
        self.ui = ui
        self.querystring = query
        self.result_count = 0
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'messages')

    def __str__(self):
        return '%s (%d threads)' % (self.querystring, self.result_count)

    def rebuild(self):
        self.result_count = self.dbman.count_messages(self.querystring)
        try:
            self.mids = self.dbman.search_message_ids(self.querystring,
                                                      sort_by=self.sort_by
                                                     )
        except NotmuchError:
            self.ui.notify('malformed query string: %s' % self.querystring,
                           'error')
            self.mids = []


        message_iterator = imap(lambda mid: self.dbman.get_message(mid),
                                self.mids)

        self.messages_walker = IteratorWalker(message_iterator,
                                              widgets.MessageWidget)
        self.listbox = urwid.ListBox(self.messages_walker)
        self.body = self.listbox

    def get_selected_message_widget(self):
        (widget, size) = self.messages_walker.get_focus()
        return widget

    def get_selected_message(self):
        widget = self.get_selected_message_widget()
        msg = None
        if widget:
            msg = widget.get_message()
        return msg

    def get_focus(self):
        return self.body.get_focus()

    def get_selection(self):
        (messagewidget, size) = self.body.get_focus()
        return messagewidget

    def unfold_matching(self, querystring):
        # TODO: do this only for already opened msgs (in mem)
        for mw in self.get_message_widgets():
            msg = mw.get_message()
            if msg.matches(querystring):
                mw.fold(visible=True)
                if 'unread' in msg.get_tags():
                    msg.remove_tags(['unread'])
                    self.ui.apply_command(commands.globals.FlushCommand())

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

    def __str__(self):
        return '%s (%d threads)' % (self.querystring, self.result_count)

    def rebuild(self):
        if self.isinitialized:
            pass
            #focusposition = self.threadlist.get_focus()[1]
        else:
            #focusposition = 0
            self.isinitialized = True

        self.result_count = self.dbman.count_messages(self.querystring)
        try:
            self.tids = self.dbman.search_thread_ids(self.querystring)
        except NotmuchError:
            self.ui.notify('malformed query string: %s' % self.querystring,
                           'error')
            self.tids = []
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


#class ThreadBuffer(Buffer):
#    def __init__(self, ui, thread):
#        self.message_count = thread.get_total_messages()
#        self.thread = thread
#        self.rebuild()
#        Buffer.__init__(self, ui, self.body, 'thread')
#
#    def __str__(self):
#        return '%s, (%d)' % (self.thread.get_subject(), self.message_count)
#
#    def get_selected_thread(self):
#        return self.thread
#
#    def _build_pile(self, acc, msg, parent, depth):
#        acc.append((parent, depth, msg))
#        for reply in self.thread.get_replies_to(msg):
#            self._build_pile(acc, reply, msg, depth + 1)
#
#    def rebuild(self):
#        self.thread.refresh()
#        # depth-first traversing the thread-tree, thereby
#        # 1) build a list of tuples (parentmsg, depth, message) in DF order
#        # 2) create a dict that counts no. of direct replies per message
#        messages = list()  # accumulator for 1,
#        childcount = {None: 0}  # accumulator for 2)
#        for msg, replies in self.thread.get_messages().items():
#            childcount[msg] = len(replies)
#        # start with all toplevel msgs, then recursively call _build_pile
#        for msg in self.thread.get_toplevel_messages():
#            self._build_pile(messages, msg, None, 0)
#            childcount[None] += 1
#
#        # go through list from 1) and pile up message widgets for all msgs.
#        # each one will be given its depth, if siblings follow and where to
#        # draw bars (siblings follow at lower depths)
#        msglines = list()
#        bars = []
#        for (num, (p, depth, m)) in enumerate(messages):
#            bars = bars[:depth]
#            childcount[p] -= 1
#
#            bars.append(childcount[p] > 0)
#            mwidget = widgets.MessageWidget(m, even=(num % 2 == 0),
#                                            depth=depth,
#                                            bars_at=bars)
#            msglines.append(mwidget)
#        self.body = urwid.ListBox(msglines)
#
#    def get_selection(self):
#        (messagewidget, size) = self.body.get_focus()
#        return messagewidget
#
#    def get_selected_message(self):
#        messagewidget = self.get_selection()
#        return messagewidget.get_message()
#
#    def get_message_widgets(self):
#        return self.body.body.contents
#
#    def get_focus(self):
#        return self.body.get_focus()
#
#    def unfold_matching(self, querystring):
#        for mw in self.get_message_widgets():
#            msg = mw.get_message()
#            if msg.matches(querystring):
#                mw.fold(visible=True)
#                if 'unread' in msg.get_tags():
#                    msg.remove_tags(['unread'])
#                    self.ui.apply_command(commands.globals.FlushCommand())


class TagListBuffer(Buffer):
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
        displayedtags = filter(self.filtfun, self.tags)
        for (num, b) in enumerate(displayedtags):
            tw = widgets.TagWidget(b)
            lines.append(urwid.Columns([('fixed', tw.width(), tw)]))
        self.taglist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.body = self.taglist

        self.taglist.set_focus(focusposition % len(displayedtags))

    def get_selected_tag(self):
        (cols, pos) = self.taglist.get_focus()
        tagwidget = cols.get_focus()
        return tagwidget.get_tag()
