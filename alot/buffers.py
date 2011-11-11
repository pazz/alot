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

import widgets
import settings
import commands
from walker import PipeWalker
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

    def cleanup(self):
        pass


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
        self.ui.logger.debug('BUFFERS')
        self.ui.logger.debug(self.ui.buffers)
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
    def __init__(self, ui, envelope):
        self.ui = ui
        self.envelope = envelope
        self.mail = envelope.construct_mail()
        self.all_headers = False
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
        self.mail = self.envelope.construct_mail()
        displayed_widgets = []
        hidden = settings.config.getstringlist('general',
                                               'envelope_headers_blacklist')
        #build lines
        lines = []
        for (k, v) in self.envelope.headers.items():
            if (k not in hidden) or self.all_headers:
                lines.append((k, decode_header(v)))

        self.header_wgt = widgets.HeadersList(lines)
        displayed_widgets.append(self.header_wgt)

        #display attachments
        lines = []
        for a in self.envelope.attachments:
            lines.append(widgets.AttachmentWidget(a, selectable=False))
        self.attachment_wgt = urwid.Pile(lines)
        displayed_widgets.append(self.attachment_wgt)

        #self.body_wgt = widgets.MessageBodyWidget(self.mail)
        self.body_wgt = urwid.Text(self.envelope.body)
        displayed_widgets.append(self.body_wgt)
        self.body = urwid.ListBox(displayed_widgets)

    def toggle_all_headers(self):
        self.all_headers = not self.all_headers
        self.rebuild()


class SearchBuffer(Buffer):
    threads = []

    def __init__(self, ui, initialquery=''):
        self.dbman = ui.dbman
        self.ui = ui
        self.querystring = initialquery
        self.result_count = 0
        self.isinitialized = False
        self.proc = None  # process that fills our pipe
        self.rebuild()
        Buffer.__init__(self, ui, self.body, 'search')

    def __str__(self):
        return '%s (%d threads)' % (self.querystring, self.result_count)

    def cleanup(self):
        self.kill_filler_process()

    def kill_filler_process(self):
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
            self.pipe, self.proc = self.dbman.get_threads(self.querystring)
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

    def __str__(self):
        return '%s, (%d)' % (self.thread.get_subject(), self.message_count)

    def get_selected_thread(self):
        return self.thread

    def _build_pile(self, acc, msg, parent, depth):
        acc.append((parent, depth, msg))
        for reply in self.thread.get_replies_to(msg):
            self._build_pile(acc, reply, msg, depth + 1)

    def rebuild(self):
        self.thread.refresh()
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

    def get_selection(self):
        (messagewidget, size) = self.body.get_focus()
        return messagewidget

    def get_selected_message(self):
        messagewidget = self.get_selection()
        return messagewidget.get_message()

    def get_message_widgets(self):
        return self.body.body.contents

    def get_focus(self):
        return self.body.get_focus()

    def unfold_matching(self, querystring):
        for mw in self.get_message_widgets():
            msg = mw.get_message()
            if msg.matches(querystring):
                mw.fold(visible=True)
                if 'unread' in msg.get_tags():
                    msg.remove_tags(['unread'])
                    self.ui.apply_command(commands.globals.FlushCommand())


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
