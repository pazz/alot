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
from urwidtrees import ArrowTree, TreeBox, NestedTree


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

    def focus_first(self):
        self.body.set_focus(0)


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
        # build lines
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

        # display attachments
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
    _REVERSE = {'oldest_first': 'newest_first',
                'newest_first': 'oldest_first'}

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

    def rebuild(self, reverse=False):
        self.isinitialized = True
        self.reversed = reverse
        self.kill_filler_process()

        self.result_count = self.dbman.count_messages(self.querystring)
        if reverse:
            order = self._REVERSE[self.sort_order]
        else:
            order = self.sort_order

        try:
            self.pipe, self.proc = self.dbman.get_threads(self.querystring,
                                                          order)
        except NotmuchError:
            self.ui.notify('malformed query string: %s' % self.querystring,
                           'error')
            self.listbox = urwid.ListBox([])
            self.body = self.listbox
            return

        self.threadlist = PipeWalker(self.pipe, ThreadlineWidget,
                                     dbman=self.dbman,
                                     reverse=reverse)

        self.listbox = urwid.ListBox(self.threadlist)
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

    def consume_pipe(self):
        while not self.threadlist.empty:
            self.threadlist._get_next_item()

    def focus_first(self):
        if not self.reversed:
            self.body.set_focus(0)
        else:
            self.rebuild(reverse=False)

    def focus_last(self):
        if self.reversed:
            self.body.set_focus(0)
        elif (self.result_count < 200) or \
                (self.sort_order not in self._REVERSE.keys()):
            self.consume_pipe()
            num_lines = len(self.threadlist.get_lines())
            self.body.set_focus(num_lines - 1)
        else:
            self.rebuild(reverse=True)


class ThreadBuffer(Buffer):
    """displays a thread as a tree of messages"""

    modename = 'thread'

    def __init__(self, ui, thread):
        """
        :param ui: main UI
        :type ui: :class:`~alot.ui.UI`
        :param thread: thread to display
        :type thread: :class:`~alot.db.Thread`
        """
        self.thread = thread
        self.message_count = thread.get_total_messages()

        # two semaphores for auto-removal of unread tag
        self._auto_unread_dont_touch_mids = set([])
        self._auto_unread_writing = False

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

        bars_att = settings.get_theming_attribute('thread', 'arrow_bars')
        heads_att = settings.get_theming_attribute('thread', 'arrow_heads')
        A = ArrowTree(self._tree,
                      indent=2,
                      childbar_offset=0,
                      arrow_tip_att=heads_att,
                      arrow_att=bars_att,
                      )
        self._nested_tree = NestedTree(A, interpret_covered=True)
        self.body = TreeBox(self._nested_tree)
        self.message_count = self.thread.get_total_messages()

    def render(self, size, focus=False):
        if settings.get('auto_remove_unread'):
            logging.debug('Tbuffer: auto remove unread tag from msg?')
            msg = self.get_selected_message()
            mid = msg.get_message_id()
            focus_pos = self.body.get_focus()[1]
            summary_pos = (self.body.get_focus()[1][0], (0,))
            cursor_on_non_summary = (focus_pos != summary_pos)
            if cursor_on_non_summary:
                if mid not in self._auto_unread_dont_touch_mids:
                    if 'unread' in msg.get_tags():
                        logging.debug('Tbuffer: removing unread')

                        def clear():
                            self._auto_unread_writing = False

                        self._auto_unread_dont_touch_mids.add(mid)
                        self._auto_unread_writing = True
                        msg.remove_tags(['unread'], afterwards=clear)
                        fcmd = commands.globals.FlushCommand(silent=True)
                        self.ui.apply_command(fcmd)
                    else:
                        logging.debug('Tbuffer: No, msg not unread')
                else:
                    logging.debug('Tbuffer: No, mid locked for autorm-unread')
            else:
                if not self._auto_unread_writing and \
                   mid in self._auto_unread_dont_touch_mids:
                    self._auto_unread_dont_touch_mids.remove(mid)
                logging.debug('Tbuffer: No, cursor on summary')
        return self.body.render(size, focus)

    def get_selected_mid(self):
        """returns Message ID of focussed message"""
        return self.body.get_focus()[1][0]

    def get_selected_message_position(self):
        """returns position of focussed message in the thread tree"""
        return self._sanitize_position((self.get_selected_mid(),))

    def get_selected_messagetree(self):
        """returns currently focussed :class:`MessageTree`"""
        return self._nested_tree[self.body.get_focus()[1][:1]]

    def get_selected_message(self):
        """returns focussed :class:`~alot.db.message.Message`"""
        return self.get_selected_messagetree()._message

    def get_messagetree_positions(self):
        """
        returns a Generator to walk through all positions of
        :class:`MessageTree` in the :class:`ThreadTree` of this buffer.
        """
        return [(pos,) for pos in self._tree.positions()]

    def messagetrees(self):
        """
        returns a Generator of all :class:`MessageTree` in the
        :class:`ThreadTree` of this buffer.
        """
        for pos in self._tree.positions():
            yield self._tree[pos]

    def refresh(self):
        """refresh and flushe caches of Thread tree"""
        self.body.refresh()

    # needed for ui.get_deep_focus..
    def get_focus(self):
        return self.body.get_focus()

    def set_focus(self, pos):
        logging.debug('setting focus to %s ', pos)
        self.body.set_focus(pos)

    def focus_first(self):
        """set focus to first message of thread"""
        self.body.set_focus(self._nested_tree.root)

    def focus_last(self):
        self.body.set_focus(next(self._nested_tree.positions(reverse=True)))

    def _sanitize_position(self, pos):
        return self._nested_tree._sanitize_position(pos,
                                                    self._nested_tree._tree)

    def focus_selected_message(self):
        """focus the summary line of currently focussed message"""
        # move focus to summary (root of current MessageTree)
        self.set_focus(self.get_selected_message_position())

    def focus_parent(self):
        """move focus to parent of currently focussed message"""
        mid = self.get_selected_mid()
        newpos = self._tree.parent_position(mid)
        if newpos is not None:
            newpos = self._sanitize_position((newpos,))
            self.body.set_focus(newpos)

    def focus_first_reply(self):
        """move focus to first reply to currently focussed message"""
        mid = self.get_selected_mid()
        newpos = self._tree.first_child_position(mid)
        if newpos is not None:
            newpos = self._sanitize_position((newpos,))
            self.body.set_focus(newpos)

    def focus_last_reply(self):
        """move focus to last reply to currently focussed message"""
        mid = self.get_selected_mid()
        newpos = self._tree.last_child_position(mid)
        if newpos is not None:
            newpos = self._sanitize_position((newpos,))
            self.body.set_focus(newpos)

    def focus_next_sibling(self):
        """focus next sibling of currently focussed message in thread tree"""
        mid = self.get_selected_mid()
        newpos = self._tree.next_sibling_position(mid)
        if newpos is not None:
            newpos = self._sanitize_position((newpos,))
            self.body.set_focus(newpos)

    def focus_prev_sibling(self):
        """
        focus previous sibling of currently focussed message in thread tree
        """
        mid = self.get_selected_mid()
        localroot = self._sanitize_position((mid,))
        if localroot == self.get_focus()[1]:
            newpos = self._tree.prev_sibling_position(mid)
            if newpos is not None:
                newpos = self._sanitize_position((newpos,))
        else:
            newpos = localroot
        if newpos is not None:
            self.body.set_focus(newpos)

    def focus_next(self):
        """focus next message in depth first order"""
        mid = self.get_selected_mid()
        newpos = self._tree.next_position(mid)
        if newpos is not None:
            newpos = self._sanitize_position((newpos,))
            self.body.set_focus(newpos)

    def focus_prev(self):
        """focus previous message in depth first order"""
        mid = self.get_selected_mid()
        localroot = self._sanitize_position((mid,))
        if localroot == self.get_focus()[1]:
            newpos = self._tree.prev_position(mid)
            if newpos is not None:
                newpos = self._sanitize_position((newpos,))
        else:
            newpos = localroot
        if newpos is not None:
            self.body.set_focus(newpos)

    def focus_property(self, prop, direction):
        """does a walk in the given direction and focuses the
        first message tree that matches the given property"""
        newpos = self.get_selected_mid()
        newpos = direction(newpos)
        while newpos is not None:
            MT = self._tree[newpos]
            if prop(MT):
                newpos = self._sanitize_position((newpos,))
                self.body.set_focus(newpos)
                break
            newpos = direction(newpos)

    def focus_next_matching(self, querystring):
        """focus next matching message in depth first order"""
        self.focus_property(lambda x: x._message.matches(querystring),
                            self._tree.next_position)

    def focus_prev_matching(self, querystring):
        """focus previous matching message in depth first order"""
        self.focus_property(lambda x: x._message.matches(querystring),
                            self._tree.prev_position)

    def focus_next_unfolded(self):
        """focus next unfolded message in depth first order"""
        self.focus_property(lambda x: not x.is_collapsed(x.root),
                            self._tree.next_position)

    def focus_prev_unfolded(self):
        """focus previous unfolded message in depth first order"""
        self.focus_property(lambda x: not x.is_collapsed(x.root),
                            self._tree.prev_position)

    def expand(self, msgpos):
        """expand message at given position"""
        MT = self._tree[msgpos]
        MT.expand(MT.root)

    def messagetree_at_position(self, pos):
        """get :class:`MessageTree` for given position"""
        return self._tree[pos[0]]

    def expand_all(self):
        """expand all messages in thread"""
        for MT in self.messagetrees():
            MT.expand(MT.root)

    def collapse(self, msgpos):
        """collapse message at given position"""
        MT = self._tree[msgpos]
        MT.collapse(MT.root)
        self.focus_selected_message()

    def collapse_all(self):
        """collapse all messages in thread"""
        for MT in self.messagetrees():
            MT.collapse(MT.root)
        self.focus_selected_message()

    def unfold_matching(self, querystring, focus_first=True):
        """
        expand all messages that match a given querystring.

        :param querystring: query to match
        :type querystring: str
        :param focus_first: set the focus to the first matching message
        :type focus_first: bool
        """
        first = None
        for MT in self.messagetrees():
            msg = MT._message
            if msg.matches(querystring):
                MT.expand(MT.root)
                if first is None:
                    first = (self._tree.position_of_messagetree(MT), MT.root)
                    self.body.set_focus(first)
            else:
                MT.collapse(MT.root)
        self.body.refresh()


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

    def focus_first(self):
        self.body.set_focus(0)

    def focus_last(self):
        allpos = self.taglist.body.positions(reverse=True)
        if allpos:
            lastpos = allpos[0]
            self.body.set_focus(lastpos)

    def get_selected_tag(self):
        """returns selected tagstring"""
        (cols, pos) = self.taglist.get_focus()
        tagwidget = cols.original_widget.get_focus()
        return tagwidget.get_tag()
