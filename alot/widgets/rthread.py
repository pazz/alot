# Copyright (C) 2014  Andres Martano <andres@inventati.org>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import logging

import urwid
from urwid import WidgetWrap, ListBox

from alot.db.utils import extract_body, decode_header, X_SIGNATURE_MESSAGE_HEADER
from alot.settings import settings
from alot.buffers import Buffer
from alot.widgets.thread import MessageTree, FocusableText
from alot.foreign.urwidtrees import Tree, ArrowTree, NestedTree
from alot.foreign.urwidtrees.widgets import TreeBox, TreeListWalker

class RTPile(urwid.Pile):
    def refresh(self):
        walker = self.contents[0][0].body
        walker.clear_cache()
        urwid.signals.emit_signal(walker, "modified")
        walker = self.contents[2][0].body
        #walker.clear_cache()
        urwid.signals.emit_signal(walker, "modified")

class RTMessageViewer(MessageTree):
    def __init__(self, message, odd=True):
        """
        :param message: Message to display
        :type message: alot.db.Message
        :param odd: theme summary widget as if this is an odd line
                    (in the message-pile)
        :type odd: bool
        """
        self._message = message
        self._odd = odd
        self.display_source = False
        self._summaryw = None
        self._bodytree = None
        self._sourcetree = None
        self.display_all_headers = False
        self._all_headers_tree = None
        self._default_headers_tree = None
        self.display_attachments = True
        self._attachments = None
        self.list = self._assemble_structure()

    def _assemble_structure(self):
        mainstruct = []
        if self.display_source:
            mainstruct.append((self._get_source(), None))
        else:
            headers = self._get_headers()

            attachmenttree = self._get_attachments()
            if attachmenttree is not None:
                mainstruct.append((attachmenttree, None))

            bodytree = self._get_body()
            if bodytree is not None:
                #mainstruct.append((self._get_body(), None))
                body = self._get_body()

        div = urwid.AttrMap(urwid.Divider(u"-"), 'bright')
        #div = FocusableText("TESTE", "default", "bright")

        structure = [
            (div, mainstruct)
        ]
        self.mainstruct = mainstruct
        return headers + body

    def _get_body(self):
        if self._bodytree is None:
            bodytxt = extract_body(self._message.get_email())
            if bodytxt:
                attr = settings.get_theming_attribute('thread', 'body')
                attr_focus = settings.get_theming_attribute( 'thread',
                                                            'body_focus')
                self._bodytree = []
                for line in bodytxt.splitlines():
                    self._bodytree.append(FocusableText(line, attr, attr_focus))
        return self._bodytree

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

    def header_part(self, content, key_attr, value_attr, gaps_attr=None):
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
        for key, value in content:
            if len(key) > max_key_len:
                max_key_len = len(key)
        for key, value in content:
            # todo : even/odd
            keyw = ('fixed', max_key_len + 1,
                    urwid.Text((key_attr, key)))
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




class RTThreadBuffer(Buffer):
    """displays a thread as a tree of messages"""

    modename = 'RTthread'

    def __init__(self, ui, thread):
        """
        :param ui: main UI
        :type ui: :class:`~alot.ui.UI`
        :param thread: thread to display
        :type thread: :class:`~alot.db.Thread`
        """
        self.ui = ui
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

        self.message_count = self.thread.get_total_messages()

        self._tree = RTThreadTree(self.thread)
        bars_att = settings.get_theming_attribute('thread', 'arrow_bars')
        heads_att = settings.get_theming_attribute('thread', 'arrow_heads')
        lite = True#settings.get_theming_attribute('thread', 'lite')
        A = ArrowTree(self._tree,
                      indent=2,
                      childbar_offset=0,
                      arrow_tip_att=heads_att,
                      arrow_att=bars_att,
                      lite=lite,
                      )
        self._nested_tree = NestedTree(A, interpret_covered=True)
        T = TreeBox(self._nested_tree)
        self.little_thread = T._outer_list

        self.end_draw()

        #lines = [] #displayedbuffers = ['a','b']
        #for (num, b) in enumerate(displayedbuffers):
        #    line = BufferlineWidget(b)
        #    if (num % 2) == 0:
        #        attr = settings.get_theming_attribute('bufferlist',
        #                                              'line_even')
        #    else:
        #        attr = settings.get_theming_attribute('bufferlist', 'line_odd')
        #    focus_att = settings.get_theming_attribute('bufferlist',
        #                                               'line_focus')
        #    buf = urwid.AttrMap(line, attr, focus_att)
        #    num = urwid.Text('A')
        #    lines.append(urwid.Columns([('fixed', 0, num), buf]))
        #    lines.append(urwid.Columns([num, buf]))

        #bufferlist = urwid.ListBox(urwid.SimpleListWalker(lines))

        #l2 = []
        #buf = urwid.AttrMap(urwid.Divider(u"!"), 'bright')
        #l2.append(buf)

        #self.list = urwid.SimpleFocusListWalker(l2)
        #list_box = urwid.ListBox(self.list)

    def create_message_viewer(self):
        #msg = self.little_thread.get_focus()[1][0]
        #msg = self.thread.get_toplevel_messages()[0]
        msg = self.get_selected_message()
        #logging.info(type(msg))
        #logging.info(msg)
        lines = RTMessageViewer(msg).list
        walker = urwid.SimpleListWalker(lines)
        return urwid.ListBox(walker)
        #T2 = TreeBox(nested_tree)

    def end_draw(self):
        self.message_viewer = self.create_message_viewer()
        pile = RTPile([
            (5,self.little_thread),
            (1, urwid.Filler(urwid.AttrMap(urwid.Divider(u"-"), 'bright'))),
            #T2._outer_list,
            self.message_viewer,
        ])
        self.body = pile

    def update_message_viewer(self):
        self.message_viewer = self.create_message_viewer()
        pile = self.body.contents
        pile.pop()
        pile.append((self.message_viewer, ('weight', 1)))


    def render(self, size, focus=False):
    #    if settings.get('auto_remove_unread'):
    #        logging.debug('Tbuffer: auto remove unread tag from msg?')
    #        msg = self.get_selected_message()
    #        mid = msg.get_message_id()
    #        focus_pos = self.body.get_focus()[1]
    #        summary_pos = (self.body.get_focus()[1][0], (0,))
    #        cursor_on_non_summary = (focus_pos != summary_pos)
    #        if cursor_on_non_summary:
    #            if mid not in self._auto_unread_dont_touch_mids:
    #                if 'unread' in msg.get_tags():
    #                    logging.debug('Tbuffer: removing unread')

    #                    def clear():
    #                        self._auto_unread_writing = False

    #                    self._auto_unread_dont_touch_mids.add(mid)
    #                    self._auto_unread_writing = True
    #                    msg.remove_tags(['unread'], afterwards=clear)
    #                    fcmd = commands.globals.FlushCommand(silent=True)
    #                    self.ui.apply_command(fcmd)
    #                else:
    #                    logging.debug('Tbuffer: No, msg not unread')
    #            else:
    #                logging.debug('Tbuffer: No, mid locked for autorm-unread')
    #        else:
    #            if not self._auto_unread_writing and \
    #               mid in self._auto_unread_dont_touch_mids:
    #                self._auto_unread_dont_touch_mids.remove(mid)
    #            logging.debug('Tbuffer: No, cursor on summary')
        return self.body.render(size, focus)

    def get_selected_line(self):
        return self.message_viewer.get_focus()[1][0]

    def get_selected_mid(self):
        """returns Message ID of focussed message"""
        return self.little_thread.get_focus()[1][0]

    def get_selected_message_position(self):
        """returns position of focussed message in the thread tree"""
        return self._sanitize_position((self.get_selected_mid(),))

    def get_selected_messagetree(self):
        """returns currently focussed :class:`MessageTree`"""
        return self._nested_tree[self.little_thread.get_focus()[1][:1]]

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

    def keypress(self, size, key):
        return self.message_viewer.keypress(size, key)

    ## needed for ui.get_deep_focus..
    #def get_focus(self):
    #    return self.body.get_focus()

    #def set_focus(self, pos):
    #    logging.debug('setting focus to %s ' % str(pos))
    #    self.body.set_focus(pos)

    #def focus_first(self):
    #    """set focus to first message of thread"""
    #    self.body.set_focus(self._nested_tree.root)

    #def focus_last(self):
    #    self.body.set_focus(next(self._nested_tree.positions(reverse=True)))

    def _sanitize_position(self, pos):
        return self._nested_tree._sanitize_position(pos,
                                                    self._nested_tree._tree)

    def _sanitize_position_message_viewer(self, pos):
        return self._nested_tree_mv._sanitize_position(pos,
                                                    self._nested_tree_mv._tree)

    #def focus_selected_message(self):
    #    """focus the summary line of currently focussed message"""
    #    # move focus to summary (root of current MessageTree)
    #    self.set_focus(self.get_selected_message_position())

    #def focus_parent(self):
    #    """move focus to parent of currently focussed message"""
    #    mid = self.get_selected_mid()
    #    newpos = self._tree.parent_position(mid)
    #    if newpos is not None:
    #        newpos = self._sanitize_position((newpos,))
    #        self.body.set_focus(newpos)
    #    i = self.little_thread.get_focus()
    #    logging.info(type(i))
    #    logging.info(i)

    #def focus_first_reply(self):
    #    """move focus to first reply to currently focussed message"""
    #    mid = self.get_selected_mid()
    #    newpos = self._tree.first_child_position(mid)
    #    if newpos is not None:
    #        newpos = self._sanitize_position((newpos,))
    #        self.body.set_focus(newpos)

    #def focus_last_reply(self):
    #    """move focus to last reply to currently focussed message"""
    #    mid = self.get_selected_mid()
    #    newpos = self._tree.last_child_position(mid)
    #    if newpos is not None:
    #        newpos = self._sanitize_position((newpos,))
    #        self.body.set_focus(newpos)

    #def focus_next_sibling(self):
    #    """focus next sibling of currently focussed message in thread tree"""
    #    mid = self.get_selected_mid()
    #    newpos = self._tree.next_sibling_position(mid)
    #    if newpos is not None:
    #        newpos = self._sanitize_position((newpos,))
    #        self.body.set_focus(newpos)
    #    i = self.little_thread.get_focus()
    #    logging.info(type(i))
    #    logging.info(i)

    #def focus_prev_sibling(self):
    #    """
    #    focus previous sibling of currently focussed message in thread tree
    #    """
    #    mid = self.get_selected_mid()
    #    localroot = self._sanitize_position((mid,))
    #    if localroot == self.get_focus()[1]:
    #        newpos = self._tree.prev_sibling_position(mid)
    #        if newpos is not None:
    #            newpos = self._sanitize_position((newpos,))
    #    else:
    #        newpos = localroot
    #    if newpos is not None:
    #        self.body.set_focus(newpos)

    def switch(self):
        """Switch focus between thread viewer and message viewer"""
        current = self.body.get_focus()
        if current == self.message_viewer:
            self.body.set_focus(self.little_thread)
        else:
            self.body.set_focus(self.message_viewer)

    def scroll_down(self):
        #self.body.set_focus(self.message_viewer)
        pos = self.message_viewer.body.get_focus()[1]
        try:
            newpos = self.message_viewer.body.next_position(pos)
            logging.info(type(newpos))
            logging.info(newpos)
            self.message_viewer.body.set_focus(newpos)
            self.refresh()
        except IndexError:
            pass

    def scroll_up(self):
        #self.body.set_focus(self.message_viewer)
        pos = self.message_viewer.body.get_focus()[1]
        try:
            newpos = self.message_viewer.body.prev_position(pos)
            logging.info(type(newpos))
            logging.info(newpos)
            self.message_viewer.body.set_focus(newpos)
            self.refresh()
        except IndexError:
            pass
    
    #def scroll_page_down(self):

    def focus_next(self):
        """focus next message in depth first order"""
        self.body.set_focus(self.little_thread)
        mid = self.get_selected_mid()
        newpos = self._tree.next_position(mid)
        if newpos is not None:
            newpos = self._sanitize_position((newpos,))
            logging.info(type(newpos))
            logging.info(newpos)
            self.little_thread.set_focus(newpos)
            self.update_message_viewer()
        #self.refresh()

    def focus_prev(self):
        """focus previous message in depth first order"""
        self.body.set_focus(self.little_thread)
        mid = self.get_selected_mid()
        mid = self.get_selected_mid()
        localroot = self._sanitize_position((mid,))
        if localroot == self.little_thread.get_focus()[1]:
            newpos = self._tree.prev_position(mid)
            if newpos is not None:
                newpos = self._sanitize_position((newpos,))
        else:
            newpos = localroot
        if newpos is not None:
            self.little_thread.set_focus(newpos)
            self.update_message_viewer()

    #def focus_property(self, prop, direction):
    #    """does a walk in the given direction and focuses the
    #    first message tree that matches the given property"""
    #    newpos = self.get_selected_mid()
    #    newpos = direction(newpos)
    #    while newpos is not None:
    #        MT = self._tree[newpos]
    #        if prop(MT):
    #            newpos = self._sanitize_position((newpos,))
    #            self.body.set_focus(newpos)
    #            break
    #        newpos = direction(newpos)

    #def focus_next_matching(self, querystring):
    #    """focus next matching message in depth first order"""
    #    self.focus_property(lambda x: x._message.matches(querystring),
    #                        self._tree.next_position)

    #def focus_prev_matching(self, querystring):
    #    """focus previous matching message in depth first order"""
    #    self.focus_property(lambda x: x._message.matches(querystring),
    #                        self._tree.prev_position)

    #def focus_next_unfolded(self):
    #    """focus next unfolded message in depth first order"""
    #    self.focus_property(lambda x: not x.is_collapsed(x.root),
    #                        self._tree.next_position)

    #def focus_prev_unfolded(self):
    #    """focus previous unfolded message in depth first order"""
    #    self.focus_property(lambda x: not x.is_collapsed(x.root),
    #                        self._tree.prev_position)

    #def expand(self, msgpos):
    #    """expand message at given position"""
    #    MT = self._tree[msgpos]
    #    MT.expand(MT.root)

    #def messagetree_at_position(self, pos):
    #    """get :class:`MessageTree` for given position"""
    #    return self._tree[pos[0]]

    #def expand_all(self):
    #    """expand all messages in thread"""
    #    for MT in self.messagetrees():
    #        MT.expand(MT.root)

    #def collapse(self, msgpos):
    #    """collapse message at given position"""
    #    MT = self._tree[msgpos]
    #    MT.collapse(MT.root)
    #    self.focus_selected_message()

    #def collapse_all(self):
    #    """collapse all messages in thread"""
    #    for MT in self.messagetrees():
    #        MT.collapse(MT.root)
    #    self.focus_selected_message()

    #def unfold_matching(self, querystring, focus_first=True):
    #    """
    #    expand all messages that match a given querystring.

    #    :param querystring: query to match
    #    :type querystring: str
    #    :param focus_first: set the focus to the first matching message
    #    :type focus_first: bool
    #    """
    #    first = None
    #    for MT in self.messagetrees():
    #        msg = MT._message
    #        if msg.matches(querystring):
    #            MT.expand(MT.root)
    #            if first is None:
    #                first = (self._tree.position_of_messagetree(MT), MT.root)
    #                self.body.set_focus(first)
    #        else:
    #            MT.collapse(MT.root)
    #    self.body.refresh()

    def oldest_matching(self, querystring, focus_first=True):
        """
        focus oldest message that match a given querystring.

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
                    self.little_thread.set_focus(first)
                    self.update_message_viewer()
                    break
        self.body.refresh()
