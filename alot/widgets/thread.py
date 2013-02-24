# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
"""
Widgets specific to thread mode
"""
import urwid
import logging

from alot.settings import settings
from alot.db.utils import decode_header
from alot.helper import tag_cmp
from alot.widgets.globals import HeadersList
from alot.widgets.globals import TagWidget
from alot.widgets.globals import AttachmentWidget
from alot.foreign.urwidtrees import Tree, SimpleTree, CollapsibleTree
from alot.db.utils import extract_body


class MessageWidget(urwid.WidgetWrap):
    """
    Flow widget that renders a :class:`~alot.db.message.Message`.
    """
    #TODO: atm this is heavily bent to work nicely with ThreadBuffer to display
    #a tree structure. A better way would be to keep this widget simple
    #(subclass urwid.Pile) and use urwids new Tree widgets
    def __init__(self, message, even=False, folded=True, raw=False,
                 all_headers=False, depth=0, bars_at=[]):
        """
        :param message: the message to display
        :type message: alot.db.Message
        :param even: use messagesummary_even theme for summary
        :type even: bool
        :param folded: fold message initially
        :type folded: bool
        :param raw: show message source initially
        :type raw: bool
        :param all_headers: show all headers initially
        :type all_headers: bool
        :param depth: number of characters to shift content to the right
        :type depth: int
        :param bars_at: defines for each column of the indentation whether to
                        use a vertical bar instead of a space.
        :type bars_at: list(bool)
        """
        self.message = message
        self.mail = self.message.get_email()

        self.depth = depth
        self.bars_at = bars_at
        self.even = even
        self.folded = folded
        self.show_raw = raw
        self.show_all_headers = all_headers

        # define subwidgets that will be created on demand
        self.sumline = None
        self.headerw = None
        self.attachmentw = None
        self.bodyw = None
        self.sourcew = None

        # set available and to be displayed headers
        self._all_headers = list(set(self.mail.keys()))
        displayed = settings.get('displayed_headers')
        self._filtered_headers = [k for k in displayed
                                  if k.lower() == 'tags' or k in self.mail]
        self._displayed_headers = None

        bars = settings.get_theming_attribute('thread', 'arrow_bars')
        self.arrow_bars_att = bars
        heads = settings.get_theming_attribute('thread', 'arrow_heads')
        self.arrow_heads_att = heads
        logging.debug(self.arrow_heads_att)

        self.rebuild()  # this will build self.pile
        urwid.WidgetWrap.__init__(self, self.pile)

    def get_focus(self):
        return self.pile.get_focus()

    def rebuild(self):
        self.sumline = self._build_sum_line()
        if not self.folded:  # only if already unfolded
            self.displayed_list = [self.sumline]
            if self.show_raw:
                srcw = self._get_source_widget()
                self.displayed_list.append(srcw)
            else:
                hw = self._get_header_widget()
                aw = self._get_attachment_widget()
                bw = self._get_body_widget()
                if hw:
                    self.displayed_list.append(hw)
                if aw:
                    self.displayed_list.append(aw)
                self.displayed_list.append(bw)
        else:
            self.displayed_list = [self.sumline]
        self.pile = urwid.Pile(self.displayed_list)
        self._w = self.pile

    def _build_sum_line(self):
        """creates/returns the widget that displays the summary line."""
        self.sumw = MessageSummaryWidget(self.message, even=self.even)
        cols = []
        bc = list()  # box_columns
        if self.depth > 1:
            bc.append(0)
            spacer = self._get_spacer(self.bars_at[1:-1])
            cols.append(spacer)
        if self.depth > 0:
            if self.bars_at[-1]:
                arrowhead = [(self.arrow_bars_att, u'\u251c'),
                             (self.arrow_heads_att, u'\u25b6')]
            else:
                arrowhead = [(self.arrow_bars_att, u'\u2514'),
                             (self.arrow_heads_att, u'\u25b6')]
            cols.append(('fixed', 2, urwid.Text(arrowhead)))
        cols.append(self.sumw)
        line = urwid.Columns(cols, box_columns=bc)
        return line

    def _get_header_widget(self):
        """creates/returns the widget that displays the mail header"""
        all_shown = (self._all_headers == self._displayed_headers)

        if self.headerw and (self.show_all_headers == all_shown):
            return self.headerw

        if self.show_all_headers:
            self._displayed_headers = self._all_headers
        else:
            self._displayed_headers = self._filtered_headers

        mail = self.message.get_email()
        # normalize values if only filtered list is shown
        norm = not (self._displayed_headers == self._all_headers)

        #build lines
        lines = []
        for key in self._displayed_headers:
            logging.debug('want header: %s' % (key))
            if key in mail:
                if key.lower() in ['cc', 'bcc', 'to']:
                    values = mail.get_all(key)
                    values = [decode_header(v, normalize=norm) for v in values]
                    lines.append((key, ', '.join(values)))
                else:
                    for value in mail.get_all(key):
                        dvalue = decode_header(value, normalize=norm)
                        lines.append((key, dvalue))
            elif key.lower() == 'tags':
                logging.debug('want tags header')
                values = []
                for t in self.message.get_tags():
                    tagrep = settings.get_tagstring_representation(t)
                    if t is not tagrep['translated']:
                        t = '%s (%s)' % (tagrep['translated'], t)
                    values.append(t)
                lines.append((key, ', '.join(values)))

        key_att = settings.get_theming_attribute('thread', 'header_key')
        value_att = settings.get_theming_attribute('thread', 'header_value')
        gaps_att = settings.get_theming_attribute('thread', 'header')
        cols = [HeadersList(lines, key_att, value_att, gaps_att)]
        bc = list()
        if self.depth:
            cols.insert(0, self._get_spacer(self.bars_at[1:]))
            bc.append(0)
            cols.insert(1, self._get_arrowhead_aligner())
            bc.append(1)
        self.headerw = urwid.Columns(cols, box_columns=bc)
        return self.headerw

    def _get_attachment_widget(self):
        if self.message.get_attachments() and not self.attachmentw:
            lines = []
            for a in self.message.get_attachments():
                cols = [AttachmentWidget(a)]
                bc = list()
                if self.depth:
                    cols.insert(0, self._get_spacer(self.bars_at[1:]))
                    bc.append(0)
                    cols.insert(1, self._get_arrowhead_aligner())
                    bc.append(1)
                lines.append(urwid.Columns(cols, box_columns=bc))
            self.attachmentw = urwid.Pile(lines)
        return self.attachmentw

    def _get_body_widget(self):
        """creates/returns the widget that displays the mail body"""
        if not self.bodyw:
            cols = [MessageBodyWidget(self.message.get_email())]
            bc = list()
            if self.depth:
                cols.insert(0, self._get_spacer(self.bars_at[1:]))
                bc.append(0)
                cols.insert(1, self._get_arrowhead_aligner())
                bc.append(1)
            self.bodyw = urwid.Columns(cols, box_columns=bc)
        return self.bodyw

    def _get_source_widget(self):
        """creates/returns the widget that displays the mail body"""
        if not self.sourcew:
            cols = [urwid.Text(self.message.get_email().as_string())]
            bc = list()
            if self.depth:
                cols.insert(0, self._get_spacer(self.bars_at[1:]))
                bc.append(0)
                cols.insert(1, self._get_arrowhead_aligner())
                bc.append(1)
            self.sourcew = urwid.Columns(cols, box_columns=bc)
        return self.sourcew

    def _get_spacer(self, bars_at):
        prefixchars = []
        length = len(bars_at)
        for b in bars_at:
            if b:
                c = u'\u2502'
            else:
                c = ' '
            prefixchars.append(('fixed', 1, urwid.SolidFill(c)))

        spacer = urwid.Columns(prefixchars, box_columns=range(length))
        spacer = urwid.AttrMap(spacer, self.arrow_bars_att)
        return ('fixed', length, spacer)

    def _get_arrowhead_aligner(self):
        if self.message.has_replies():
            aligner = u'\u2502'
        else:
            aligner = ' '
        aligner = urwid.SolidFill(aligner)
        return ('fixed', 1, urwid.AttrMap(aligner, self.arrow_bars_att))

    def selectable(self):
        return True

    def keypress(self, size, key):
        return self.pile.keypress(size, key)

    def get_message(self):
        """get contained :class`~alot.db.message.Message`"""
        return self.message

    def get_email(self):
        """get contained :class:`email <email.Message>`"""
        return self.message.get_email()


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

        thread_tags = message.get_thread().get_tags(intersection=True)
        outstanding_tags = set(message.get_tags()).difference(thread_tags)
        tag_widgets = [TagWidget(t, attr, focus_att) for t in outstanding_tags]
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


class MessageBodyWidget(urwid.AttrMap):
    """
    displays printable parts of an email
    """

    def __init__(self, message):
        self._message = message
        bodytxt = extract_body(message.get_email())
        att = settings.get_theming_attribute('thread', 'body')
        urwid.AttrMap.__init__(self, urwid.Text(bodytxt), att)


class DictList(SimpleTree):
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
        #calc max length of key-string
        for key, value in content:
            if len(key) > max_key_len:
                max_key_len = len(key)
        for key, value in content:
            ##todo : even/odd
            keyw = ('fixed', max_key_len + 1,
                    urwid.Text((key_attr, key)))
            valuew = urwid.Text((value_attr, value))
            line = urwid.Columns([keyw, valuew])
            if gaps_attr is not None:
                line = urwid.AttrMap(line, gaps_attr)
            structure.append((line, None))
        SimpleTree.__init__(self, structure)


class MessageTree(CollapsibleTree):
    def __init__(self, message, odd=True):
        self._message = message
        self._summaryw = MessageSummaryWidget(message, even=(not odd))

        self.display_headers = 'default'
        self._all_headers_tree = None
        self._default_headers_tree = None
        self.display_attachments = True

        CollapsibleTree.__init__(self, SimpleTree(self._assemble_structure()))

    def _assemble_structure(self):
        mainstruct = [
            (self._get_headers(), None),
            (self._get_body(), None),
        ]
        if self.display_attachments:
            for a in self._message.get_attachments():
                mainstruct.insert(1, (AttachmentWidget(a), None))
        structure = [
            (self._summaryw, mainstruct)
        ]
        return structure

    def collapse_if_matches(self, querystring):
        self.set_position_collapsed(
            self.root, self._message.matches(querystring))

    def _get_body(self):
        return MessageBodyWidget(self._message)

    def _get_headers(self):
        if self.display_headers == 'all':
            if self._all_headers_tree is None:
                self._all_headers_tree = self.construct_header_pile()
            ret = self._all_headers_tree
        elif self.display_headers == 'default':
            if self._default_headers_tree is None:
                headers = settings.get('displayed_headers')
                self._default_headers_tree = self.construct_header_pile(headers)
            ret = self._default_headers_tree
        return ret

    def construct_header_pile(self, headers=None, normalize=True):
        mail = self._message.get_email()
        if headers is None:
            headers = mail.keys()
        else:
            headers = [k for k in headers if
                       k.lower() == 'tags' or k in mail]

        lines = []
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

        key_att = settings.get_theming_attribute('thread', 'header_key')
        value_att = settings.get_theming_attribute('thread', 'header_value')
        gaps_att = settings.get_theming_attribute('thread', 'header')
        return DictList(lines, key_att, value_att, gaps_att)


class ThreadTree(Tree):
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
