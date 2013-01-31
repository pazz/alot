# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import urwid
import os
from notmuch import NotmuchError
import logging

from settings import settings
import commands
from walker import PipeWalker
from helper import shorten_author_string
from db.errors import NonexistantObjectError

from alot.widgets.globals import TagWidget
from alot.widgets.globals import HeadersList
from alot.widgets.globals import AttachmentWidget
from alot.widgets.bufferlist import BufferlineWidget
from alot.widgets.search import ThreadlineWidget
from alot.widgets.thread import ThreadTree
from alot.foreign.urwidtrees import ArrowTree, TreeBox, NestedTree, CollapsibleArrowTree


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
        """called before buffer is closed"""
        pass

    def get_info(self):
        """
        return dict of meta infos about this buffer.
        This can be requested to be displayed in the statusbar.
        """
        return {}


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
            line = BufferlineWidget(b)
            if (num % 2) == 0:
                attr = settings.get_theming_attribute('bufferlist',
                                                      'line_even')
            else:
                attr = settings.get_theming_attribute('bufferlist', 'line_odd')
            focus_att = settings.get_theming_attribute('bufferlist',
                                                       'line_focus')
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

    def get_info(self):
        info = {}
        info['to'] = self.envelope.get('To', fallback='unset')
        return info

    def cleanup(self):
        if self.envelope.tmpfile:
            os.unlink(self.envelope.tmpfile.name)

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
                description += ', with key ' + sign_key.uids[0].uid
            lines.append(('GPG sign', description))

        if self.envelope.encrypt:
            description = 'Yes'
            encrypt_keys = self.envelope.encrypt_keys.values()
            if len(encrypt_keys) == 1:
                description += ', with key '
            elif len(encrypt_keys) > 1:
                description += ', with keys '
            first_key = True
            for key in encrypt_keys:
                if key is not None:
                    if first_key:
                        first_key = False
                    else:
                        description += ', '
                    if len(key.subkeys) > 0:
                        description += key.uids[0].uid
            lines.append(('GPG encrypt', description))

        # add header list widget iff header values exists
        if lines:
            key_att = settings.get_theming_attribute('envelope', 'header_key')
            value_att = settings.get_theming_attribute('envelope',
                                                       'header_value')
            gaps_att = settings.get_theming_attribute('envelope', 'header')
            self.header_wgt = HeadersList(lines, key_att, value_att, gaps_att)
            displayed_widgets.append(self.header_wgt)

        #display attachments
        lines = []
        for a in self.envelope.attachments:
            lines.append(AttachmentWidget(a, selectable=False))
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

    def get_info(self):
        info = {}
        info['querystring'] = self.querystring
        info['result_count'] = self.result_count
        info['result_count_positive'] = 's' * (not (self.result_count == 1))
        return info

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
            self.listbox = urwid.ListBox([])
            self.body = self.listbox
            return

        self.threadlist = PipeWalker(self.pipe, ThreadlineWidget,
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

    def get_info(self):
        info = {}
        info['subject'] = self.thread.get_subject()
        info['authors'] = self.thread.get_authors_string()
        info['tid'] = self.thread.get_thread_id()
        info['message_count'] = self.message_count
        return info

    def get_selected_thread(self):
        """returns the displayed :class:`~alot.db.Thread`"""
        return self.thread

    def rebuild(self):
        try:
            self.thread.refresh()
        except NonexistantObjectError:
            self.body = urwid.SolidFill()
            self.message_count = 0
            return

        self._tree = ThreadTree(self.thread)
        A = ArrowTree(self._tree)
        self._nested_tree =NestedTree(A, interpret_covered=True)
        self.body = TreeBox(self._nested_tree)
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

    def get_messagetree_positions(self):
        """
        """
        return [(pos,) for pos in self._tree.positions()]

    def refresh(self):
        self.body.refresh()

    def messagetrees(self):
        for pos in self._tree.positions():
            yield self._tree[pos]

    def get_focus(self):
        return self.body.get_focus()

    def expand(self, msgpos):
        MT = self._tree[msgpos]
        MT.expand(MT.root)

    def messagetree_at_position(self, pos):
        return self._tree[pos[0]]

    def expand_and_remove_unread(self, pos):
        messagetree = self.messagetree_at_position(pos)
        msg = messagetree._message
        messagetree.expand(messagetree.root)
        if 'unread' in msg.get_tags():
            msg.remove_tags(['unread'])
            self.ui.apply_command(commands.globals.FlushCommand())

    def expand_all(self):
        for MT in self.messagetrees():
            MT.expand(MT.root)

    def collapse(self, msgpos):
        MT = self._tree[msgpos]
        MT.collapse(MT.root)

    def collapse_all(self):
        for MT in self.messagetrees():
            MT.collapse(MT.root)

    def unfold_matching(self, querystring, focus_first=True):
        """
        unfolds messages that match a given querystring.

        :param querystring: query to match
        :type querystring: str
        :param focus_first: set the focus to the first matching message
        :type focus_first: bool
        """
        return
        first = None
        for MT in self.messagetrees():
            msg = MT._message
            if msg.matches(querystring):
                MT.expand(MT.root)
                if first is None:
                    logging.debug('BODY %s' % self.body)
                    self.body.set_focus((pos, MT.root))
                if 'unread' in msg.get_tags():
                    msg.remove_tags(['unread'])
                    self.ui.apply_command(commands.globals.FlushCommand())
            else:
                MT.collapse(MT.root)


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
            if (num % 2) == 0:
                attr = settings.get_theming_attribute('taglist', 'line_even')
            else:
                attr = settings.get_theming_attribute('taglist', 'line_odd')
            focus_att = settings.get_theming_attribute('taglist', 'line_focus')

            tw = TagWidget(b, attr, focus_att)
            rows = [('fixed', tw.width(), tw)]
            if tw.hidden:
                rows.append(urwid.Text(b + ' [hidden]'))
            elif tw.translated is not b:
                rows.append(urwid.Text('(%s)' % b))
            line = urwid.Columns(rows, dividechars=1)
            line = urwid.AttrMap(line, attr, focus_att)
            lines.append(line)

        self.taglist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.body = self.taglist

        self.taglist.set_focus(focusposition % len(displayedtags))

    def get_selected_tag(self):
        """returns selected tagstring"""
        (cols, pos) = self.taglist.get_focus()
        tagwidget = cols.original_widget.get_focus()
        return tagwidget.get_tag()
