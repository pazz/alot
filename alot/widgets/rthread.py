# Copyright (C) 2014  Andres Martano <andres@inventati.org>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import logging

import urwid
from urwid import WidgetWrap, ListBox, Text

from alot.db.utils import extract_body, decode_header, X_SIGNATURE_MESSAGE_HEADER
from alot.settings import settings
from alot.widgets.globals import AttachmentWidget
from alot.widgets.thread import MessageTree, FocusableText
from alot.foreign.urwidtrees import Tree, ArrowTree, NestedTree
from alot.foreign.urwidtrees.widgets import TreeBox, TreeListWalker

class RTPile(urwid.Pile):
    def refresh(self):
        walker = self.contents[0][0].body
        walker.clear_cache()
        urwid.signals.emit_signal(walker, "modified")
        walker = self.contents[2][0].body
        urwid.signals.emit_signal(walker, "modified")

class RTMessageViewer(urwid.ListBox):
    def __init__(self, message):
        """
        :param message: Message to display
        :type message: alot.db.Message
        """
        self._message = message
        self.display_source = False
        self._bodytxt = None
        self._sourcetree = None
        self.display_all_headers = False
        self._all_headers = None
        self._default_headers = None
        self._attachments = None

        content = self._assemble_structure()
        self.walker = urwid.SimpleListWalker(content)
        urwid.ListBox.__init__(self, self.walker)
        #self.body = self._assemble_structure()

    #def render(self, size, focus=False):
    #    return self.body.render(size, focus)

    def reassemble(self):
        self.walker[:] = self._assemble_structure()

    def _assemble_structure(self):
        mainstruct = []
        if self.display_source:
            mainstruct += self._get_source()
        else:
            mainstruct += self._get_headers()

            attachmenttree = self._get_attachments()
            if attachmenttree is not None:
                mainstruct += attachmenttree

            bodytree = self._get_body()
            if bodytree is not None:
                mainstruct.append(self._get_body())

        return mainstruct

    def _get_source(self):
        if self._sourcetree is None:
            sourcetxt = self._message.get_email().as_string()
            attr = settings.get_theming_attribute('thread', 'body')
            attr_focus = settings.get_theming_attribute('thread', 'body_focus')
            self._sourcetree = []
            for line in sourcetxt.splitlines():
                self._sourcetree.append(FocusableText(line, attr, attr_focus))
        return self._sourcetree

    def _get_body(self):
        if self._bodytxt is None:
            bodytxt = extract_body(self._message.get_email())
            if bodytxt:
                attr = settings.get_theming_attribute('thread', 'body')
                t = urwid.Text(bodytxt)
                self._bodytxt = urwid.AttrMap(t, attr)
        return self._bodytxt

    def _get_headers(self):
        if self.display_all_headers is True:
            if self._all_headers is None:
                self._all_headers = self.construct_header_pile()
            ret = self._all_headers
        else:
            if self._default_headers is None:
                headers = settings.get('displayed_headers')
                self._default_headers = self.construct_header_pile(
                    headers)
            ret = self._default_headers
        return ret

    def _get_attachments(self):
        if self._attachments is None:
            alist = []
            for a in self._message.get_attachments():
                alist.append(AttachmentWidget(a))
        return alist

    def construct_header_pile(self, headers=None, normalize=True):
        mail = self._message.get_email()
        lines = []

        if headers is None:
            # collect all header/value pairs in the order they appear
            headers = mail.keys()
            for key, value in mail.items():
                dvalue = decode_header(value, normalize=normalize)
                lines.append((key, dvalue))
        else:
            # only a selection of headers should be displayed.
            # use order of the `headers` parameter
            for key in headers:
                if key in mail:
                    if key.lower() in ['cc', 'bcc', 'to']:
                        values = mail.get_all(key)
                        values = [decode_header(
                            v, normalize=normalize) for v in values]
                        lines.append((key, ', '.join(values)))
                    else:
                        for value in mail.get_all(key):
                            dvalue = decode_header(value, normalize=normalize)
                            lines.append((key, dvalue))
                elif key.lower() == 'tags':
                    logging.debug('want tags header')
                    values = []
                    for t in self._message.get_tags():
                        tagrep = settings.get_tagstring_representation(t)
                        if t is not tagrep['translated']:
                            t = '%s (%s)' % (tagrep['translated'], t)
                        values.append(t)
                    lines.append((key, ', '.join(values)))

        # OpenPGP pseudo headers
        if mail[X_SIGNATURE_MESSAGE_HEADER]:
            lines.append(('PGP-Signature', mail[X_SIGNATURE_MESSAGE_HEADER]))

        key_att = settings.get_theming_attribute('thread', 'header_key')
        value_att = settings.get_theming_attribute('thread', 'header_value')
        gaps_att = settings.get_theming_attribute('thread', 'header')
        return self.header_part(lines, key_att, value_att, gaps_att)

    def header_part(self, headerslist, key_attr, value_attr, gaps_attr=None):
        """
        :param headerslist: list of key/value pairs to display
        :type headerslist: list of (str, str)
        :param key_attr: theming attribute to use for keys
        :type key_attr: urwid.AttrSpec
        :param value_attr: theming attribute to use for values
        :type value_attr: urwid.AttrSpec
        :param gaps_attr: theming attribute to wrap lines in
        :type gaps_attr: urwid.AttrSpec
        """
        max_key_len = 1
        structure = []
        # calc max length of key-string
        for key, value in headerslist:
            if len(key) > max_key_len:
                max_key_len = len(key)
        for key, value in headerslist:
            # todo : even/odd
            keyw = ('fixed', max_key_len + 1, urwid.Text((key_attr, key)))
            valuew = urwid.Text((value_attr, value))
            line = urwid.Columns([keyw, valuew])
            if gaps_attr is not None:
                line = urwid.AttrMap(line, gaps_attr)
            structure.append(line)
        return structure

class RTTreeBox(WidgetWrap):
    """
    A widget that displays a given :class:`Tree`.
    This is essentially a :class:`ListBox` with the ability to move the focus
    based on directions in the Tree and to collapse/expand subtrees if
    possible.

    TreeBox interprets `left/right` as well as `page up/`page down` to move the
    focus to parent/first child and next/previous sibling respectively. All
    other keys are passed to the underlying ListBox.
    """

    def __init__(self, tree, focus=None):
        """
        :param tree: tree of widgets to be displayed.
        :type tree: Tree
        :param focus: initially focussed position
        """
        self._tree = tree
        self._walker = TreeListWalker(tree)
        self._outer_list = ListBox(self._walker)
        if focus is not None:
            self._outer_list.set_focus(focus)
        self.__super.__init__(self._outer_list)

    # Widget API
    def get_focus(self):
        return self._outer_list.get_focus()

    def set_focus(self, pos):
        return self._outer_list.set_focus(pos)

    def refresh(self):
        self._walker.clear_cache()
        signals.emit_signal(self._walker, "modified")

    def keypress(self, size, key):
        key = self._outer_list.keypress(size, key)
        if key in ['left', 'right', '[', ']', '-', '+', 'C', 'E', ]:
            if key == 'left':
                self.focus_parent()
            elif key == 'right':
                self.focus_first_child()
            elif key == '[':
                self.focus_prev_sibling()
            elif key == ']':
                self.focus_next_sibling()
            elif key == '-':
                self.collapse_focussed()
            elif key == '+':
                self.expand_focussed()
            elif key == 'C':
                self.collapse_all()
            elif key == 'E':
                self.expand_all()
            # This is a hack around ListBox misbehaving:
            # it seems impossible to set the focus without calling keypress as
            # otherwise the change becomes visible only after the next render()
            return self._outer_list.keypress(size, None)
        else:
            return self._outer_list.keypress(size, key)

    # Collapse operations
    def collapse_focussed(self):
        """
        Collapse currently focussed position; works only if the underlying
        tree allows it.
        """
        if implementsCollapseAPI(self._tree):
            w, focuspos = self.get_focus()
            self._tree.collapse(focuspos)
            self._walker.clear_cache()
            self.refresh()

    def expand_focussed(self):
        """
        Expand currently focussed position; works only if the underlying
        tree allows it.
        """
        if implementsCollapseAPI(self._tree):
            w, focuspos = self.get_focus()
            self._tree.expand(focuspos)
            self._walker.clear_cache()
            self.refresh()

    def collapse_all(self):
        """
        Collapse all positions; works only if the underlying tree allows it.
        """
        if implementsCollapseAPI(self._tree):
            self._tree.collapse_all()
            self.set_focus(self._tree.root)
            self._walker.clear_cache()
            self.refresh()

    def expand_all(self):
        """
        Expand all positions; works only if the underlying tree allows it.
        """
        if implementsCollapseAPI(self._tree):
            self._tree.expand_all()
            self._walker.clear_cache()
            self.refresh()

    # Tree based focus movement
    def focus_parent(self):
        """move focus to parent node of currently focussed one"""
        w, focuspos = self.get_focus()
        parent = self._tree.parent_position(focuspos)
        if parent is not None:
            self.set_focus(parent)

    def focus_first_child(self):
        """move focus to first child of currently focussed one"""
        w, focuspos = self.get_focus()
        child = self._tree.first_child_position(focuspos)
        if child is not None:
            self.set_focus(child)

    def focus_last_child(self):
        """move focus to last child of currently focussed one"""
        w, focuspos = self.get_focus()
        child = self._tree.last_child_position(focuspos)
        if child is not None:
            self.set_focus(child)

    def focus_next_sibling(self):
        """move focus to next sibling of currently focussed one"""
        w, focuspos = self.get_focus()
        sib = self._tree.next_sibling_position(focuspos)
        if sib is not None:
            self.set_focus(sib)

    def focus_prev_sibling(self):
        """move focus to previous sibling of currently focussed one"""
        w, focuspos = self.get_focus()
        sib = self._tree.prev_sibling_position(focuspos)
        if sib is not None:
            self.set_focus(sib)

    def focus_next(self):
        """move focus to next position (DFO)"""
        w, focuspos = self.get_focus()
        next = self._tree.next_position(focuspos)
        if next is not None:
            self.set_focus(next)

    def focus_prev(self):
        """move focus to previous position (DFO)"""
        w, focuspos = self.get_focus()
        prev = self._tree.prev_position(focuspos)
        if prev is not None:
            self.set_focus(prev)


class RTMessageTree(MessageTree):
    def _assemble_structure(self):
        structure = [
            (self._get_summary(), None)
        ]
        return structure



class RTThreadTree(Tree):
    """
    :class:`Tree` that parses a given :class:`alot.db.Thread` into a tree of
    :class:`MessageTrees <MessageTree>` that display this threads individual
    messages. As MessageTreess are *not* urwid widgets themself this is to be
    used in combination with :class:`NestedTree` only.
    """
    def __init__(self, thread):
        self._thread = thread
        self.root = thread.get_toplevel_messages()[0].get_message_id()
        self._parent_of = {}
        self._first_child_of = {}
        self._last_child_of = {}
        self._next_sibling_of = {}
        self._prev_sibling_of = {}
        self._message = {}

        def accumulate(msg, odd=True):
            """recursively read msg and its replies"""
            mid = msg.get_message_id()
            self._message[mid] = RTMessageTree(msg, odd)
            odd = not odd
            last = None
            self._first_child_of[mid] = None
            for reply in thread.get_replies_to(msg):
                rid = reply.get_message_id()
                if self._first_child_of[mid] is None:
                    self._first_child_of[mid] = rid
                self._parent_of[rid] = mid
                self._prev_sibling_of[rid] = last
                self._next_sibling_of[last] = rid
                last = rid
                odd = accumulate(reply, odd)
            self._last_child_of[mid] = last
            return odd

        last = None
        for msg in thread.get_toplevel_messages():
            mid = msg.get_message_id()
            self._prev_sibling_of[mid] = last
            self._next_sibling_of[last] = mid
            accumulate(msg)
            last = mid
        self._next_sibling_of[last] = None

    # Tree API
    def __getitem__(self, pos):
        return self._message.get(pos, None)

    def parent_position(self, pos):
        return self._parent_of.get(pos, None)

    def first_child_position(self, pos):
        return self._first_child_of.get(pos, None)

    def last_child_position(self, pos):
        return self._last_child_of.get(pos, None)

    def next_sibling_position(self, pos):
        return self._next_sibling_of.get(pos, None)

    def prev_sibling_position(self, pos):
        return self._prev_sibling_of.get(pos, None)

    def position_of_messagetree(self, mt):
        return mt._message.get_message_id()
