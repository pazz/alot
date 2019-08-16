# Copyright (C) 2011-2018  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import asyncio
import urwid
import logging
from urwidtrees import ArrowTree, TreeBox, NestedTree

from .buffer import Buffer
from ..settings.const import settings
from ..widgets.thread import ThreadTree
from .. import commands
from ..db.errors import NonexistantObjectError


class ThreadBuffer(Buffer):
    """displays a thread as a tree of messages."""

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

        self._indent_width = settings.get('thread_indent_replies')
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

    def __str__(self):
        return '[thread] %s (%d message%s)' % (self.thread.get_subject(),
                                               self.message_count,
                                               's' * (self.message_count > 1))

    def translated_tags_str(self, intersection=False):
        tags = self.thread.get_tags(intersection=intersection)
        trans = [settings.get_tagstring_representation(tag)['translated']
                 for tag in tags]
        return ' '.join(trans)

    def get_info(self):
        info = {}
        info['subject'] = self.thread.get_subject()
        info['authors'] = self.thread.get_authors_string()
        info['tid'] = self.thread.get_thread_id()
        info['message_count'] = self.message_count
        info['thread_tags'] = self.translated_tags_str()
        info['intersection_tags'] = self.translated_tags_str(intersection=True)
        return info

    def get_selected_thread(self):
        """Return the displayed :class:`~alot.db.Thread`."""
        return self.thread

    def rebuild(self):
        try:
            self.thread.refresh()
        except NonexistantObjectError:
            self.body = urwid.SolidFill()
            self.message_count = 0
            return

        self._tree = ThreadTree(self.thread)

        # define A to be the tree to be wrapped by a NestedTree and displayed.
        # We wrap the thread tree into an ArrowTree for decoration if
        # indentation was requested and otherwise use it as is.
        if self._indent_width == 0:
            A = self._tree
        else:
            # we want decoration.
            bars_att = settings.get_theming_attribute('thread', 'arrow_bars')
            # only add arrow heads if there is space (indent > 1).
            heads_char = None
            heads_att = None
            if self._indent_width > 1:
                heads_char = u'\u27a4'
                heads_att = settings.get_theming_attribute('thread',
                                                           'arrow_heads')
            A = ArrowTree(
                self._tree,
                indent=self._indent_width,
                childbar_offset=0,
                arrow_tip_att=heads_att,
                arrow_tip_char=heads_char,
                arrow_att=bars_att)

        self._nested_tree = NestedTree(A, interpret_covered=True)
        self.body = TreeBox(self._nested_tree)
        self.message_count = self.thread.get_total_messages()

    def render(self, size, focus=False):
        if self.message_count == 0:
            return self.body.render(size, focus)

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
                        asyncio.get_event_loop().create_task(
                            self.ui.apply_command(fcmd))
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
        """Return Message ID of focussed message."""
        return self.body.get_focus()[1][0]

    def get_selected_message_position(self):
        """Return position of focussed message in the thread tree."""
        return self._sanitize_position((self.get_selected_mid(),))

    def get_selected_messagetree(self):
        """Return currently focussed :class:`MessageTree`."""
        return self._nested_tree[self.body.get_focus()[1][:1]]

    def get_selected_message(self):
        """Return focussed :class:`~alot.db.message.Message`."""
        return self.get_selected_messagetree()._message

    def get_messagetree_positions(self):
        """
        Return a Generator to walk through all positions of
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
        """Refresh and flush caches of Thread tree."""
        self.body.refresh()

    # needed for ui.get_deep_focus..
    def get_focus(self):
        "Get the focus from the underlying body widget."
        return self.body.get_focus()

    def set_focus(self, pos):
        "Set the focus in the underlying body widget."
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
