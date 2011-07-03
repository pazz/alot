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
import tempfile
import os
import re
from datetime import datetime

from settings import config
from settings import get_mime_handler
from helper import shorten
from helper import pretty_datetime
from helper import cmd_output


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
        line = '[' + buffer.typename + '] ' + str(buffer)
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


class PromptWidget(urwid.AttrMap):
    def __init__(self, prefix, text='', completer=None):
        self.completer = completer
        leftpart = urwid.Text(prefix, align='left')
        self.editpart = urwid.Edit(edit_text=text)
        self.start_completion_pos = len(text)
        self.completion_results = None
        both = urwid.Columns(
            [
                ('fixed', len(prefix) + 1, leftpart),
                ('weight', 1, self.editpart),
            ])
        urwid.AttrMap.__init__(self, both, 'prompt', 'prompt')

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


class MessageWidget(urwid.WidgetWrap):
    """flow widget that displays a single message"""
    def __init__(self, message, even=False, unfold_body=False,
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
        self.bodyw = None
        self.displayed_list = [self.sumline]
        if unfold_header:
            self.displayed_list.append(self.get_header_widget())
        if unfold_body:
            self.displayed_list.append(self.get_body_widget())

        #build pile and call super constructor
        self.pile = urwid.Pile(self.displayed_list)
        urwid.WidgetWrap.__init__(self, self.pile)

        # in case the message is yet unread, remove this tag
        if 'unread' in message.get_tags():
            message.remove_tags(['unread'])

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

    def toggle_header(self):
        """toggles if message headers are shown"""
        hw = self._get_header_widget()
        if hw in self.displayed_list:
            self.displayed_list.remove(hw)
        else:
            self.displayed_list.insert(1, hw)
        self.rebuild()

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

    def keypress(self, size, key):
        if key == 'h':
            self.toggle_header()
        elif key == 'enter':
            self.toggle_header()
            self.toggle_body()
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
        urwid.WidgetWrap.__init__(self, urwid.Text(str(self)))

    def __str__(self):
        prefix = "-  "
        if self.folded:
            prefix = '+  '
        aname, aaddress = self.message.get_author()
        return "%s%s (%s)" % (prefix, aname,
                            pretty_datetime(self.message.datetime))

    def toggle_folded(self):
        self.folded = not self.folded
        self._w = urwid.Text(str(self))

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageHeaderWidget(urwid.AttrMap):
    """displays a "key:value\n" list of email headers"""

    def __init__(self, eml, displayed_headers=None):
        """
        :param eml: the email
        :type eml: email.Message
        :param displayed_headers: a whitelist of header fields to display
        :type state: list(str)
        """
        self.eml = eml
        headerlines = []
        max_key_len = 1
        if not displayed_headers:
            displayed_headers = eml.keys()
        for key in displayed_headers:
            if key in eml:
                if len(key) > max_key_len:
                    max_key_len = len(key)
        for key in displayed_headers:
            #todo: parse from,cc,bcc seperately into name-addr-widgets
            if key in eml:
                value = reduce(lambda x,y: x+y[0],
                        email.header.decode_header(eml[key]), '')
                #sanitize it a bit:
                value = value.replace('\t','')
                value = value.replace('\r','')
                keyw = ('fixed', max_key_len+1,
                        urwid.Text(('message_header_key',key)))
                valuew = urwid.Text(('message_header_value',value))
                line = urwid.Columns([keyw,valuew])
                headerlines.append(line)
        urwid.AttrMap.__init__(self, urwid.Pile(headerlines), 'message_header')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageBodyWidget(urwid.AttrMap):
    """displays printable parts of an email"""

    def __init__(self, eml):
        """
        :param eml: the email
        :type eml: email.Message
        """
        self.eml = eml
        bodytxt = ''
        for part in self.eml.walk():
            ctype = part.get_content_type()
            if ctype == 'text/plain':
                bodytxt += part.get_payload(None, True)
            elif ctype == 'text/html':
                #get mime handler
                handler = get_mime_handler(ctype, key='view',
                                           interactive=False)
                #open tempfile:
                tmpfile = tempfile.NamedTemporaryFile(delete=False,
                                                      suffix='.html')
                #write payload to tmpfile
                tmpfile.write(part.get_payload(None, True))
                #create and call external command
                cmd = handler % tmpfile.name
                rendered = cmd_output(cmd)
                #remove tempfile
                tmpfile.close()
                os.unlink(tmpfile.name)
                bodytxt += rendered
        urwid.AttrMap.__init__(self, urwid.Text(bodytxt), 'message_body')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
