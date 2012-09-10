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
import alot.db.message as message
from alot.helper import tag_cmp
from alot.widgets.globals import HeadersList
from alot.widgets.globals import TagWidget
from alot.widgets.globals import AttachmentWidget


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
                values = self.message.get_tags()
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

    def __init__(self, msg):
        bodytxt = message.extract_body(msg)
        att = settings.get_theming_attribute('thread', 'body')
        urwid.AttrMap.__init__(self, urwid.Text(bodytxt), att)
