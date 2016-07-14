# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
"""
Widgets specific to thread mode
"""
import urwid
import logging

from alot.settings import settings
from alot.db.utils import decode_header, X_SIGNATURE_MESSAGE_HEADER
from alot.helper import tag_cmp
from alot.widgets.globals import TagWidget
from alot.widgets.globals import AttachmentWidget
from urwidtrees import Tree, SimpleTree, CollapsibleTree
from alot.db.utils import extract_body


class MessageSummaryWidget(urwid.WidgetWrap):
    """
    one line summary of a :class:`~alot.db.message.Message`.
    """

    def __init__(self, message, even=True):
        """
        :param message: a message
        :type message: alot.db.Message
        :param even: even entry in a pile of messages? Used for theming.
        :type even: bool
        """
        self.message = message
        self.even = even
        if even:
            attr = settings.get_theming_attribute('thread', 'summary', 'even')
        else:
            attr = settings.get_theming_attribute('thread', 'summary', 'odd')
        focus_att = settings.get_theming_attribute('thread', 'summary',
                                                   'focus')
        cols = []

        sumstr = self.__str__()
        txt = urwid.Text(sumstr)
        cols.append(txt)

        if settings.get('msg_summary_hides_threadwide_tags'):
            thread_tags = message.get_thread().get_tags(intersection=True)
            outstanding_tags = set(message.get_tags()).difference(thread_tags)
            tag_widgets = [TagWidget(t, attr, focus_att)
                           for t in outstanding_tags]
        else:
            tag_widgets = [TagWidget(t, attr, focus_att)
                           for t in message.get_tags()]
        tag_widgets.sort(tag_cmp, lambda tag_widget: tag_widget.translated)
        for tag_widget in tag_widgets:
            if not tag_widget.hidden:
                cols.append(('fixed', tag_widget.width(), tag_widget))
        line = urwid.AttrMap(urwid.Columns(cols, dividechars=1), attr,
                             focus_att)
        urwid.WidgetWrap.__init__(self, line)

    def __str__(self):
        author, address = self.message.get_author()
        date = self.message.get_datestring()
        rep = author if author != '' else address
        if date is not None:
            rep += " (%s)" % date
        return rep

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class FocusableText(urwid.WidgetWrap):
    """Selectable Text used for nodes in our example"""
    def __init__(self, txt, att, att_focus):
        t = urwid.Text(txt)
        w = urwid.AttrMap(t, att, att_focus)
        urwid.WidgetWrap.__init__(self, w)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class TextlinesList(SimpleTree):
    def __init__(self, content, attr=None, attr_focus=None):
        """
        :class:`SimpleTree` that contains a list of all-level-0 Text widgets
        for each line in content.
        """
        structure = []
        for line in content.splitlines():
            structure.append((FocusableText(line, attr, attr_focus), None))
        SimpleTree.__init__(self, structure)


class DictList(SimpleTree):
    """
    :class:`SimpleTree` that displays key-value pairs.

    The structure will obey the Tree API but will not actually be a tree
    but a flat list: It contains one top-level node (displaying the k/v pair in
    Columns) per pair. That is, the root will be the first pair,
    its sibblings will be the other pairs and first|last_child will always
    be None.
    """
    def __init__(self, content, key_attr, value_attr, gaps_attr=None):
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
            structure.append((line, None))
        SimpleTree.__init__(self, structure)


class MessageTree(CollapsibleTree):
    """
    :class:`Tree` that displays contents of a single :class:`alot.db.Message`.

    Its root node is a :class:`MessageSummaryWidget`, and its child nodes
    reflect the messages content (parts for headers/attachments etc).

    Collapsing this message corresponds to showing the summary only.
    """
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
        self._maintree = SimpleTree(self._assemble_structure())
        CollapsibleTree.__init__(self, self._maintree)

    def get_message(self):
        return self._message

    def reassemble(self):
        self._maintree._treelist = self._assemble_structure()

    def refresh(self):
        self._summaryw = None
        self.reassemble()

    def debug(self):
        logging.debug('collapsed %s', self.is_collapsed(self.root))
        logging.debug('display_source %s', self.display_source)
        logging.debug('display_all_headers %s', self.display_all_headers)
        logging.debug('display_attachements %s', self.display_attachments)
        logging.debug('AHT %s', str(self._all_headers_tree))
        logging.debug('DHT %s', str(self._default_headers_tree))
        logging.debug('MAINTREE %s', str(self._maintree._treelist))

    def _assemble_structure(self):
        mainstruct = []
        if self.display_source:
            mainstruct.append((self._get_source(), None))
        else:
            mainstruct.append((self._get_headers(), None))

            attachmenttree = self._get_attachments()
            if attachmenttree is not None:
                mainstruct.append((attachmenttree, None))

            bodytree = self._get_body()
            if bodytree is not None:
                mainstruct.append((self._get_body(), None))

        structure = [
            (self._get_summary(), mainstruct)
        ]
        return structure

    def collapse_if_matches(self, querystring):
        """
        collapse (and show summary only) if the :class:`alot.db.Message`
        matches given `querystring`
        """
        self.set_position_collapsed(
            self.root, self._message.matches(querystring))

    def _get_summary(self):
        if self._summaryw is None:
            self._summaryw = MessageSummaryWidget(
                self._message, even=(not self._odd))
        return self._summaryw

    def _get_source(self):
        if self._sourcetree is None:
            sourcetxt = self._message.get_email().as_string()
            att = settings.get_theming_attribute('thread', 'body')
            att_focus = settings.get_theming_attribute('thread', 'body_focus')
            self._sourcetree = TextlinesList(sourcetxt, att, att_focus)
        return self._sourcetree

    def _get_body(self):
        if self._bodytree is None:
            bodytxt = extract_body(self._message.get_email())
            if bodytxt:
                att = settings.get_theming_attribute('thread', 'body')
                att_focus = settings.get_theming_attribute(
                    'thread', 'body_focus')
                self._bodytree = TextlinesList(bodytxt, att, att_focus)
        return self._bodytree

    def replace_bodytext(self, txt):
        """display txt instead of current msg 'body'"""
        if txt:
            att = settings.get_theming_attribute('thread', 'body')
            att_focus = settings.get_theming_attribute('thread', 'body_focus')
            self._bodytree = TextlinesList(txt, att, att_focus)

    def _get_headers(self):
        if self.display_all_headers is True:
            if self._all_headers_tree is None:
                self._all_headers_tree = self.construct_header_pile()
            ret = self._all_headers_tree
        else:
            if self._default_headers_tree is None:
                headers = settings.get('displayed_headers')
                self._default_headers_tree = self.construct_header_pile(
                    headers)
            ret = self._default_headers_tree
        return ret

    def _get_attachments(self):
        if self._attachments is None:
            alist = []
            for a in self._message.get_attachments():
                alist.append((AttachmentWidget(a), None))
            if alist:
                self._attachments = SimpleTree(alist)
        return self._attachments

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
        return DictList(lines, key_att, value_att, gaps_att)


class ThreadTree(Tree):
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
            self._message[mid] = MessageTree(msg, odd)
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
