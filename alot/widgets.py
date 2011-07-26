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
import email
import urwid
from urwid.command_map import command_map

from settings import config
from helper import shorten
from helper import pretty_datetime
import message


class ThreadlineWidget(urwid.AttrMap):
#TODO: receive a thread here. needs change in calling walker
    def __init__(self, tid, dbman):
        self.dbman = dbman
        self.thread = dbman.get_thread(tid)
        self.rebuild()
        urwid.AttrMap.__init__(self, self.columns,
                               'threadline', 'threadline_focus')

    def rebuild(self):
        cols = []
        datestring = pretty_datetime(self.thread.get_newest_date()).rjust(10)
        self.date_w = urwid.AttrMap(urwid.Text(datestring), 'threadline_date')
        cols.append(('fixed', len(datestring), self.date_w))

        mailcountstring = "(%d)" % self.thread.get_total_messages()
        self.mailcount_w = urwid.AttrMap(urwid.Text(mailcountstring),
                                   'threadline_mailcount')
        cols.append(('fixed', len(mailcountstring), self.mailcount_w))

        tagsstring = " ".join(self.thread.get_tags())
        self.tags_w = urwid.AttrMap(urwid.Text(tagsstring), 'threadline_tags')
        if tagsstring:
            cols.append(('fixed', len(tagsstring), self.tags_w))

        authors = self.thread.get_authors() or '(None)'
        maxlength = config.getint('general', 'authors_maxlength')
        authorsstring = shorten(authors, maxlength)
        self.authors_w = urwid.AttrMap(urwid.Text(authorsstring),
                                       'threadline_authors')
        cols.append(('fixed', len(authorsstring), self.authors_w))

        subjectstring = self.thread.get_subject()
        self.subject_w = urwid.AttrMap(urwid.Text(subjectstring, wrap='clip'),
                                 'threadline_subject')
        if subjectstring:
            cols.append(self.subject_w)

        self.columns = urwid.Columns(cols, dividechars=1)
        self.original_widget = self.columns

    def render(self, size, focus=False):
        if focus:
            self.date_w.set_attr_map({None: 'threadline_date_focus'})
            self.mailcount_w.set_attr_map({None:
                                           'threadline_mailcount_focus'})
            self.tags_w.set_attr_map({None: 'threadline_tags_focus'})
            self.authors_w.set_attr_map({None: 'threadline_authors_focus'})
            self.subject_w.set_attr_map({None: 'threadline_subject_focus'})
        else:
            self.date_w.set_attr_map({None: 'threadline_date'})
            self.mailcount_w.set_attr_map({None: 'threadline_mailcount'})
            self.tags_w.set_attr_map({None: 'threadline_tags'})
            self.authors_w.set_attr_map({None: 'threadline_authors'})
            self.subject_w.set_attr_map({None: 'threadline_subject'})
        return urwid.AttrMap.render(self, size, focus)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_thread(self):
        return self.thread


class BufferlineWidget(urwid.Text):
    def __init__(self, buffer):
        self.buffer = buffer
        line = '[' + buffer.typename + '] ' + unicode(buffer)
        urwid.Text.__init__(self, line, wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_buffer(self):
        return self.buffer


class TagWidget(urwid.Text):
    def __init__(self, tag):
        self.tag = tag
        urwid.Text.__init__(self, tag, wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_tag(self):
        return self.tag


class CompleteEdit(urwid.Edit):
    # TODO: defaulttext: visible in darker font, tpe it with tab/enter
    def __init__(self, completer, edit_text=u'', **kwargs):
        self.completer = completer
        if not isinstance(edit_text, unicode):
            edit_text = unicode(edit_text, errors='replace')
        self.start_completion_pos = len(edit_text)
        self.completion_results = None
        urwid.Edit.__init__(self, edit_text=edit_text, **kwargs)

    def keypress(self, size, key):
        cmd = command_map[key]
        if cmd in ['next selectable', 'prev selectable']:
            pos = self.start_completion_pos
            original = self.edit_text[:pos]
            if not self.completion_results:  # not in completion mode
                self.completion_results = [''] + \
                    self.completer.complete(original)
                self.focus_in_clist = 1
            else:
                if cmd == 'next selectable':
                    self.focus_in_clist += 1
                else:
                    self.focus_in_clist -= 1
            if len(self.completion_results) > 1:
                suffix = self.completion_results[self.focus_in_clist %
                                          len(self.completion_results)]
                self.set_edit_text(original + suffix)
                self.edit_pos += len(suffix)
            else:
                self.set_edit_text(original + ' ')
                self.edit_pos += 1
                self.start_completion_pos = self.edit_pos
                self.completion_results = None
        else:
            result = urwid.Edit.keypress(self, size, key)
            self.start_completion_pos = self.edit_pos
            self.completion_results = None
            return result


class MessageWidget(urwid.WidgetWrap):
    """flow widget that displays a single message"""
    def __init__(self, message, even=False, unfold_body=False,
                 unfold_attachments=False,
                 unfold_header=False, depth=0, bars_at=[]):
        """
        :param message: the message to display
        :type message: alot.db.Message
        :param even: use messagesummary_even theme for summary
        :type even: boolean
        :param unfold_body: initially show message body
        :type unfold_body: boolean
        :param unfold_header: initially show message headers
        :type unfold_header: boolean
        :param depth: number of characters to shift content to the right
        :type depth: int
        :param bars_at: list of positions smaller than depth where horizontal
        ars are used instead of spaces.
        :type bars_at: list(int)
        """
        self.message = message
        self.depth = depth
        self.bars_at = bars_at
        self.even = even

        # build the summary line, header and body will be created on demand
        self.sumline = self._build_sum_line()
        self.headerw = None
        self.attachmentw = None
        self.bodyw = None
        self.displayed_list = [self.sumline]
        if unfold_header:
            self.displayed_list.append(self.get_header_widget())
        if unfold_body:
            self.displayed_list.append(self.get_body_widget())

        if unfold_attachments:
            self.displayed_list.append(self.get_attachment_widget())
        #build pile and call super constructor
        self.pile = urwid.Pile(self.displayed_list)
        urwid.WidgetWrap.__init__(self, self.pile)

    def rebuild(self):
        self.pile = urwid.Pile(self.displayed_list)
        self._w = self.pile

    def _build_sum_line(self):
        """creates/returns the widget that displays the summary line."""
        self.sumw = MessageSummaryWidget(self.message)
        if self.even:
            attr = 'messagesummary_even'
        else:
            attr = 'messagesummary_odd'
        cols = []
        bc = list()  # box_columns
        if self.depth > 1:
            bc.append(0)
            cols.append(self._get_spacer(self.bars_at[1:-1]))
        if self.depth > 0:
            if self.bars_at[-1]:
                arrowhead = u'\u251c\u25b6'
            else:
                arrowhead = u'\u2514\u25b6'
            cols.append(('fixed', 2, urwid.Text(arrowhead)))
        cols.append(self.sumw)
        line = urwid.AttrMap(urwid.Columns(cols, box_columns=bc),
                             attr, 'messagesummary_focus')
        return line

    def _get_header_widget(self):
        """creates/returns the widget that displays the mail header"""
        if not self.headerw:
            displayed = config.getstringlist('general', 'displayed_headers')
            cols = [MessageHeaderWidget(self.message.get_email(), displayed)]
            bc = list()
            if self.depth:
                cols.insert(0, self._get_spacer(self.bars_at[1:]))
                bc.append(0)
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
                lines.append(urwid.Columns(cols, box_columns=bc))
            self.attachmentw = urwid.Pile(lines)
        return self.attachmentw

        attachments = message.get_attachments()

    def _get_body_widget(self):
        """creates/returns the widget that displays the mail body"""
        if not self.bodyw:
            cols = [MessageBodyWidget(self.message.get_email())]
            bc = list()
            if self.depth:
                cols.insert(0, self._get_spacer(self.bars_at[1:]))
                bc.append(0)
            self.bodyw = urwid.Columns(cols, box_columns=bc)
        return self.bodyw

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
        return ('fixed', length, spacer)

    def toggle_attachments(self):
        """toggles if message headers are shown"""
        hw = self._get_attachment_widget()
        if hw:
            if hw in self.displayed_list:
                self.displayed_list.remove(hw)
            else:
                self.displayed_list.insert(1, hw)
            self.rebuild()

    def toggle_header(self):
        """toggles if message headers are shown"""
        hw = self._get_header_widget()
        if hw in self.displayed_list:
            self.displayed_list.remove(hw)
        else:
            self.displayed_list.insert(1, hw)
        self.rebuild()

    def toggle_full_header(self):
        """toggles if message headers are shown"""
        hw = self._get_header_widget().widget_list[-1]
        hw.toggle_all()

    def toggle_body(self):
        """toggles if message body is shown"""
        bw = self._get_body_widget()
        if bw in self.displayed_list:
            self.displayed_list.remove(bw)
        else:
            self.displayed_list.append(bw)
        self.sumw.toggle_folded()
        self.rebuild()

    def selectable(self):
        return True

    #TODO: this needs to go in favour of a binding in the buffer!
    def keypress(self, size, key):
        if key == 'h':
            self.toggle_header()
        elif key == 'enter':
            self.toggle_attachments()
            self.toggle_header()
            self.toggle_body()
        elif key == 'H':
            self.toggle_full_header()
        else:
            return self.pile.keypress(size, key)

    def get_message(self):
        """get contained message
        returns: alot.db.Message"""
        return self.message

    def get_email(self):
        """get contained email
        returns: email.Message"""
        return self.message.get_email()


class MessageSummaryWidget(urwid.WidgetWrap):
    """a one line summary of a message"""

    def __init__(self, message, folded=True):
        """
        :param message: the message to summarize
        :type message: alot.db.Message
        """
        self.message = message
        self.folded = folded
        sumstr = self.__str__()
        urwid.WidgetWrap.__init__(self, urwid.Text(sumstr))

    def __str__(self):
        prefix = "-  "
        if self.folded:
            prefix = '+  '
        return u"%s%s" % (prefix, unicode(self.message))

    def toggle_folded(self):
        self.folded = not self.folded
        self._w = urwid.Text(self.__str__())

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageHeaderWidget(urwid.AttrMap):
    """
    displays a "key:value\n" list of email headers.
    RFC 2822 style encoded values are decoded into utf8 first.
    """

    def __init__(self, eml, displayed_headers=None):
        """
        :param eml: the email
        :type eml: email.Message
        :param displayed_headers: a whitelist of header fields to display
        :type state: list(str)
        """
        self.eml = eml
        self.display_all = False
        self.displayed_headers = displayed_headers
        headerlines = self._build_lines(displayed_headers)
        urwid.AttrMap.__init__(self, urwid.Pile(headerlines), 'message_header')

    def toggle_all(self):
        if self.display_all:
            self.display_all = False
            headerlines = self._build_lines(self.displayed_headers)
        else:
            self.display_all = True
            headerlines = self._build_lines(None)
        self._w = urwid.Pile(headerlines)

    def _build_lines(self, displayed):
        max_key_len = 1
        headerlines = []
        if not displayed:
            displayed = self.eml.keys()
        for key in displayed:
            if key in self.eml:
                if len(key) > max_key_len:
                    max_key_len = len(key)
        for key in displayed:
            #todo: parse from,cc,bcc seperately into name-addr-widgets
            if key in self.eml:
                valuelist = email.header.decode_header(self.eml[key])
                value = ''
                for v, enc in valuelist:
                    if enc:
                        value = value + v.decode(enc)
                    else:
                        value = value + v
                #sanitize it a bit:
                value = value.replace('\t', '')
                value = value.replace('\r', '')
                keyw = ('fixed', max_key_len + 1,
                        urwid.Text(('message_header_key', key)))
                valuew = urwid.Text(('message_header_value', value))
                line = urwid.Columns([keyw, valuew])
                headerlines.append(line)
        return headerlines

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageBodyWidget(urwid.AttrMap):
    """displays printable parts of an email"""

    def __init__(self, msg):
        bodytxt = message.extract_body(msg)
        urwid.AttrMap.__init__(self, urwid.Text(bodytxt), 'message_body')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class AttachmentWidget(urwid.WidgetWrap):
    def __init__(self, attachment):
        self.attachment = attachment
        widget = urwid.AttrMap(urwid.Text(unicode(attachment)),
                               'message_attachment')
        urwid.WidgetWrap.__init__(self, widget)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
