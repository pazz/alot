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
from urwid import Text
from urwid import Edit
from urwid import Pile
from urwid import Columns
from urwid import AttrMap
from urwid import WidgetWrap
from urwid import ListBox
from urwid import SimpleListWalker
from datetime import datetime
import logging

import settings
from helper import shorten
from helper import pretty_datetime


class ThreadlineWidget(AttrMap):
    def __init__(self, tid, dbman):
        self.dbman = dbman
        self.thread = dbman.get_thread(tid)
        self.rebuild()
        AttrMap.__init__(self, self.columns, 'threadline', 'threadline_focus')

    def rebuild(self):
        cols = []
        datestring = pretty_datetime(self.thread.get_newest_date())
        self.date_w = AttrMap(Text(datestring), 'threadline_date')
        cols.append(('fixed', len(datestring), self.date_w))

        mailcountstring = "(%d)" % self.thread.get_total_messages()
        self.mailcount_w = AttrMap(Text(mailcountstring),
                                   'threadline_mailcount')
        cols.append(('fixed', len(mailcountstring), self.mailcount_w))

        tagsstring = " ".join(self.thread.get_tags())
        self.tags_w = AttrMap(Text(tagsstring), 'threadline_tags')
        if tagsstring:
            cols.append(('fixed', len(tagsstring), self.tags_w))

        authors = self.thread.get_authors() or '(None)'
        authorsstring = shorten(authors, settings.authors_maxlength)
        self.authors_w = AttrMap(Text(authorsstring), 'threadline_authors')
        cols.append(('fixed', len(authorsstring), self.authors_w))

        subjectstring = self.thread.get_subject()
        self.subject_w = AttrMap(Text(subjectstring, wrap='clip'),
                                 'threadline_subject')
        if subjectstring:
            cols.append(self.subject_w)

        self.columns = Columns(cols, dividechars=1)
        self.original_widget = self.columns

    def render(self, size, focus=False):
        if focus:
            self.date_w.set_attr_map({None: 'threadline_date_linefocus'})
            self.mailcount_w.set_attr_map({None:
                                           'threadline_mailcount_linefocus'})
            self.tags_w.set_attr_map({None: 'threadline_tags_linefocus'})
            self.authors_w.set_attr_map({None: 'threadline_authors_linefocus'})
            self.subject_w.set_attr_map({None: 'threadline_subject_linefocus'})
        else:
            self.date_w.set_attr_map({None: 'threadline_date'})
            self.mailcount_w.set_attr_map({None: 'threadline_mailcount'})
            self.tags_w.set_attr_map({None: 'threadline_tags'})
            self.authors_w.set_attr_map({None: 'threadline_authors'})
            self.subject_w.set_attr_map({None: 'threadline_subject'})
        return AttrMap.render(self, size, focus)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_thread(self):
        return self.thread


class BufferlineWidget(Text):
    def __init__(self, buffer):
        self.buffer = buffer
        Text.__init__(self, str(buffer), wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_buffer(self):
        return self.buffer


class TagWidget(Text):
    def __init__(self, tag):
        self.tag = tag
        Text.__init__(self, tag, wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_tag(self):
        return self.tag


class PromptWidget(AttrMap):
    def __init__(self, prefix, text='', completer=None):
        self.completer = completer
        leftpart = Text(prefix, align='left')
        self.editpart = Edit(edit_text=text)
        self.start_completion_pos = len(text)
        self.completion_results = None
        both = Columns(
            [
                ('fixed', len(prefix) + 1, leftpart),
                ('weight', 1, self.editpart),
            ])
        AttrMap.__init__(self, both, 'prompt', 'prompt')

    def set_input(self, txt):
        return self.editpart.set_edit_text(txt)

    def get_input(self):
        return self.editpart.get_edit_text()

    def keypress(self, size, key):
        if key in ['tab', 'shift tab']:
            if self.completer:
                pos = self.start_completion_pos
                original = self.editpart.edit_text[:pos]
                if not self.completion_results:  # not in completion mode
                    self.completion_results = [''] + \
                        self.completer.complete(original)
                    self.focus_in_clist = 1
                else:
                    if key == 'tab':
                        self.focus_in_clist += 1
                    else:
                        self.focus_in_clist -= 1
                if len(self.completion_results) > 1:
                    suffix = self.completion_results[self.focus_in_clist %
                                              len(self.completion_results)]
                    self.editpart.set_edit_text(original + suffix)
                    self.editpart.edit_pos += len(suffix)
                else:
                    self.editpart.set_edit_text(original + ' ')
                    self.editpart.edit_pos += 1
                    self.start_completion_pos = self.editpart.edit_pos
                    self.completion_results = None
        else:
            result = self.editpart.keypress(size, key)
            self.start_completion_pos = self.editpart.edit_pos
            self.completion_results = None
            return result


class MessageWidget(WidgetWrap):
    def __init__(self, message, even=False, unfold_body=False,
                 unfold_header=False, depth=0, bars_at=[]):
        self.message = message
        self.depth = depth
        self.bars_at = bars_at
        self.even = even

        # build the summary line, header and body will be created on demand
        self.sumline = self._build_sum_line()
        self.headerw = None
        self.bodyw = None
        self.displayed_list = [self.sumline]
        if unfold_header:
            self.displayed_list.append(self.get_header_widget())
        if unfold_body:
            self.displayed_list.append(self.get_body_widget())

        #build pile and call super constructor
        self.pile = Pile(self.displayed_list)
        WidgetWrap.__init__(self, self.pile)

        # in case the message is yet unread, remove this tag
        if 'unread' in message.get_tags():
            message.remove_tags(['unread'])

    def rebuild(self):
        self.pile = Pile(self.displayed_list)
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
            cols.append(('fixed', 2, Text(arrowhead)))
        cols.append(self.sumw)
        line = urwid.AttrMap(urwid.Columns(cols, box_columns=bc),
                             attr, 'messagesummary_focus')
        return line

    def _get_header_widget(self):
        """creates/returns the widget that displays the mail header"""
        if not self.headerw:
            cols = [MessageHeaderWidget(self.message.get_email())]
            bc = list()
            if self.depth:
                cols.insert(0, self._get_spacer(self.bars_at[1:]))
                bc.append(0)
            self.headerw = urwid.Columns(cols, box_columns=bc)
        return self.headerw

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
        logging.info(bars_at)
        length = len(bars_at)
        for b in bars_at:
            if b:
                c = u'\u2502'
            else:
                c = ' '
            prefixchars.append(('fixed', 1, urwid.SolidFill(c)))

        spacer = urwid.Columns(prefixchars, box_columns=range(length))
        return ('fixed', length, spacer)

    def toggle_header(self):
        hw = self._get_header_widget()
        if hw in self.displayed_list:
            self.displayed_list.remove(hw)
        else:
            self.displayed_list.insert(1, hw)
        self.rebuild()

    def toggle_body(self):
        bw = self._get_body_widget()
        if bw in self.displayed_list:
            self.displayed_list.remove(bw)
        else:
            self.displayed_list.append(bw)
        self.sumw.toggle_folded()
        self.rebuild()

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == 'h':
            self.toggle_header()
        elif key == 'enter':
            self.toggle_body()
        else:
            return self.pile.keypress(size, key)

    def get_message(self):
        return self.message

    def get_email(self):
        return self.message.get_email()


class MessageSummaryWidget(WidgetWrap):
    """a one line summary of a message, top of the message widget pile."""

    def __init__(self, message, folded=True):
        self.message = message
        self.folded = folded
        WidgetWrap.__init__(self, Text(str(self)))

    def __str__(self):
        prefix = "-  "
        if self.folded:
            prefix = '+  '
        return prefix + str(self.message)

    def toggle_folded(self):
        self.folded = not self.folded
        self._w = Text(str(self))

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageHeaderWidget(AttrMap):
    def __init__(self, eml):
        self.eml = eml
        headerlines = []
        for line in settings.displayed_headers:
            if line in eml:
                headerlines.append('%s:%s' % (line, eml.get(line)))
        headertxt = '\n'.join(headerlines)
        AttrMap.__init__(self, Text(headertxt), 'message_header')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageBodyWidget(AttrMap):
    def __init__(self, eml):
        self.eml = eml
        bodytxt = ''.join(email.iterators.body_line_iterator(self.eml))
        AttrMap.__init__(self, Text(bodytxt), 'message_body')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
