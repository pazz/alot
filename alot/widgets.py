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
import logging

from settings import config
from helper import shorten_author_string
from helper import pretty_datetime
from helper import tag_cmp
from helper import string_decode
import message


class DialogBox(urwid.WidgetWrap):
    def __init__(self, body, title, bodyattr=None, titleattr=None):
        self.body = urwid.LineBox(body)
        self.title = urwid.Text(title)
        if titleattr is not None:
            self.title = urwid.AttrMap(self.title, titleattr)
        if bodyattr is not None:
            self.body = urwid.AttrMap(self.body, bodyattr)

        box = urwid.Overlay(self.title, self.body,
                            align='center',
                            valign='top',
                            width=len(title),
                            height=None,
                           )
        urwid.WidgetWrap.__init__(self, box)

    def selectable(self):
        return self.body.selectable()

    def keypress(self, size, key):
        return self.body.keypress(size, key)


class CatchKeyWidgetWrap(urwid.WidgetWrap):
    def __init__(self, widget, key, on_catch, relay_rest=True):
        urwid.WidgetWrap.__init__(self, widget)
        self.key = key
        self.relay = relay_rest
        self.on_catch = on_catch

    def selectable(self):
        return True

    def keypress(self, size, key):
        logging.debug('CATCH KEY: %s' % key)
        logging.debug('relay: %s' % self.relay)
        if key == self.key:
            self.on_catch()
        elif self._w.selectable() and self.relay:
            return self._w.keypress(size, key)


class ThreadlineWidget(urwid.AttrMap):
    def __init__(self, tid, dbman):
        self.dbman = dbman
        #logging.debug('tid: %s' % tid)
        self.thread = dbman.get_thread(tid)
        #logging.debug('tid: %s' % self.thread)
        self.tag_widgets = []
        self.display_content = config.getboolean('general',
                                    'display_content_in_threadline')
        self.rebuild()
        urwid.AttrMap.__init__(self, self.columns,
                               'threadline', 'threadline_focus')

    def rebuild(self):
        cols = []
        if self.thread:
          newest = self.thread.get_newest_date()
        else:
          newest = None
        if newest == None:
            datestring = u' ' * 10
        else:
            formatstring = config.get('general', 'timestamp_format')
            if formatstring:
                datestring = newest.strftime(formatstring)
            else:
                datestring = pretty_datetime(newest).rjust(10)
        self.date_w = urwid.AttrMap(urwid.Text(datestring), 'threadline_date')
        cols.append(('fixed', len(datestring), self.date_w))

        if self.thread:
          mailcountstring = "(%d)" % self.thread.get_total_messages()
        else:
          mailcountstring = "(?)"
        self.mailcount_w = urwid.AttrMap(urwid.Text(mailcountstring),
                                   'threadline_mailcount')
        cols.append(('fixed', len(mailcountstring), self.mailcount_w))

        if self.thread:
          self.tag_widgets = [TagWidget(tag) for tag in self.thread.get_tags()]
        else:
          self.tag_widgets = []
        self.tag_widgets.sort(tag_cmp,
                              lambda tag_widget: tag_widget.translated)
        for tag_widget in self.tag_widgets:
            cols.append(('fixed', tag_widget.width(), tag_widget))

        if self.thread:
          authors = self.thread.get_authors() or '(None)'
        else:
          authors = '(None)'
        maxlength = config.getint('general', 'authors_maxlength')
        authorsstring = shorten_author_string(authors, maxlength)
        self.authors_w = urwid.AttrMap(urwid.Text(authorsstring),
                                       'threadline_authors')
        cols.append(('fixed', len(authorsstring), self.authors_w))

        if self.thread:
          subjectstring = self.thread.get_subject().strip()
        else:
          subjectstring = ''
        self.subject_w = urwid.AttrMap(urwid.Text(subjectstring, wrap='clip'),
                                 'threadline_subject')
        if subjectstring:
            cols.append(('weight', 2, self.subject_w))

        if self.display_content:
            if self.thread:
                msgs = self.thread.get_messages().keys()
            else:
                msgs = []
            msgs.sort()
            lastcontent = ' '.join([m.get_text_content() for m in msgs])
            contentstring = lastcontent.replace('\n', ' ').strip()
            self.content_w = urwid.AttrMap(urwid.Text(contentstring,
                                                      wrap='clip'),
                                           'threadline_content')
            cols.append(self.content_w)

        self.columns = urwid.Columns(cols, dividechars=1)
        self.original_widget = self.columns

    def render(self, size, focus=False):
        if focus:
            self.date_w.set_attr_map({None: 'threadline_date_focus'})
            self.mailcount_w.set_attr_map({None:
                                           'threadline_mailcount_focus'})
            for tw in self.tag_widgets:
                tw.set_focussed()
            self.authors_w.set_attr_map({None: 'threadline_authors_focus'})
            self.subject_w.set_attr_map({None: 'threadline_subject_focus'})
            if self.display_content:
                self.content_w.set_attr_map({None: 'threadline_content_focus'})
        else:
            self.date_w.set_attr_map({None: 'threadline_date'})
            self.mailcount_w.set_attr_map({None: 'threadline_mailcount'})
            for tw in self.tag_widgets:
                tw.set_unfocussed()
            self.authors_w.set_attr_map({None: 'threadline_authors'})
            self.subject_w.set_attr_map({None: 'threadline_subject'})
            if self.display_content:
                self.content_w.set_attr_map({None: 'threadline_content'})
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
        line = '[' + buffer.typename + '] ' + buffer.__str__()
        urwid.Text.__init__(self, line, wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_buffer(self):
        return self.buffer


class TagWidget(urwid.AttrMap):
    def __init__(self, tag):
        self.tag = tag
        self.translated = config.get('tag-translate', tag, fallback=tag)
        self.txt = urwid.Text(self.translated.encode('utf-8'), wrap='clip')
        normal = config.get_tagattr(tag)
        focus = config.get_tagattr(tag, focus=True)
        urwid.AttrMap.__init__(self, self.txt, normal, focus)

    def width(self):
        # evil voodoo hotfix for double width chars that may
        # lead e.g. to strings with length 1 that need width 2
        return self.txt.pack()[0]

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_tag(self):
        return self.tag

    def set_focussed(self):
        self.set_attr_map({None: config.get_tagattr(self.tag, focus=True)})

    def set_unfocussed(self):
        self.set_attr_map({None: config.get_tagattr(self.tag)})


class ChoiceWidget(urwid.Text):
    def __init__(self, choices, callback, cancel=None, select=None):
        self.choices = choices
        self.callback = callback
        self.cancel = cancel
        self.select = select

        items = []
        for k, v in choices.items():
            if v == select and select != None:
                items.append('[%s]:%s' % (k, v))
            else:
                items.append('(%s):%s' % (k, v))
        urwid.Text.__init__(self, ' '.join(items))

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == 'select' and self.select != None:
            self.callback(self.select)
        elif key == 'cancel' and self.cancel != None:
            self.callback(self.cancel)
        elif key in self.choices:
            self.callback(self.choices[key])
        else:
            return key


class CompleteEdit(urwid.Edit):
    def __init__(self, completer, on_exit, edit_text=u'',
                 history=None, **kwargs):
        self.completer = completer
        self.on_exit = on_exit
        self.history = list(history)  # we temporarily add stuff here
        self.historypos = None

        if not isinstance(edit_text, unicode):
            edit_text = string_decode(edit_text)
        self.start_completion_pos = len(edit_text)
        self.completions = None
        urwid.Edit.__init__(self, edit_text=edit_text, **kwargs)

    def keypress(self, size, key):
        # if we tabcomplete
        if key in ['tab', 'shift tab'] and self.completer:
            # if not already in completion mode
            if not self.completions:
                self.completions = [(self.edit_text, self.edit_pos)] + \
                    self.completer.complete(self.edit_text, self.edit_pos)
                self.focus_in_clist = 1
            else:  # otherwise tab through results
                if key == 'tab':
                    self.focus_in_clist += 1
                else:
                    self.focus_in_clist -= 1
            if len(self.completions) > 1:
                ctext, cpos = self.completions[self.focus_in_clist %
                                          len(self.completions)]
                self.set_edit_text(ctext)
                self.set_edit_pos(cpos)
            else:
                self.edit_pos += 1
                if self.edit_pos >= len(self.edit_text):
                    self.edit_text += ' '
                self.completions = None
        elif key in ['up', 'down']:
            if self.history:
                if self.historypos == None:
                    self.history.append(self.edit_text)
                    self.historypos = len(self.history) - 1
                if key == 'cursor up':
                    self.historypos = (self.historypos + 1) % len(self.history)
                else:
                    self.historypos = (self.historypos - 1) % len(self.history)
                self.set_edit_text(self.history[self.historypos])
        elif key == 'select':
            self.on_exit(self.edit_text)
        elif key == 'cancel':
            self.on_exit(None)
        else:
            result = urwid.Edit.keypress(self, size, key)
            self.completions = None
            return result


class MessageWidget(urwid.WidgetWrap):
    """flow widget that displays a single message"""
    #TODO: atm this is heavily bend to work nicely with ThreadBuffer to display
    #a tree structure. A better way would be to keep this widget simple
    #(subclass urwid.Pile) and use urwids new Tree widgets
    def __init__(self, message, even=False, folded=True, depth=0, bars_at=[]):
        """
        :param message: the message to display
        :type message: alot.db.Message
        :param even: use messagesummary_even theme for summary
        :type even: boolean
        :param unfolded: unfold message initially
        :type unfolded: boolean
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
        self.folded = folded

        # build the summary line, header and body will be created on demand
        self.sumline = self._build_sum_line()
        self.headerw = None
        self.attachmentw = None
        self.bodyw = None
        self.displayed_list = [self.sumline]
        #build pile and call super constructor
        self.pile = urwid.Pile(self.displayed_list)
        urwid.WidgetWrap.__init__(self, self.pile)
        #unfold if requested
        if not folded:
            self.fold(visible=True)

    def get_focus(self):
        return self.pile.get_focus()

    #TODO re-read tags
    def rebuild(self):
        self.pile = urwid.Pile(self.displayed_list)
        self._w = self.pile

    def _build_sum_line(self):
        """creates/returns the widget that displays the summary line."""
        self.sumw = MessageSummaryWidget(self.message, even=self.even)
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
        line = urwid.Columns(cols, box_columns=bc)
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

    def toggle_full_header(self):
        """toggles if message headers are shown"""
        # caution: this is very ugly, it's supposed to get the headerwidget.
        col = self._get_header_widget().widget_list
        hws = [h for h in col if isinstance(h, MessageHeaderWidget)][0]
        hws.toggle_all()

    def fold(self, visible=False):
        hw = self._get_header_widget()
        aw = self._get_attachment_widget()
        bw = self._get_body_widget()
        if visible:
            if self.folded:  # only if not already unfolded
                self.displayed_list.append(hw)
                if aw:
                    self.displayed_list.append(aw)
                self.displayed_list.append(bw)
                self.folded = False
                self.rebuild()
        else:
            if not self.folded:
                self.displayed_list.remove(hw)
                if aw:
                    self.displayed_list.remove(aw)
                self.displayed_list.remove(bw)
                self.folded = True
                self.rebuild()

    def selectable(self):
        return True

    def keypress(self, size, key):
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

    def __init__(self, message, even=True):
        """
        :param message: the message to summarize
        :type message: alot.db.Message
        """
        self.message = message
        self.even = even
        if even:
            attr = 'messagesummary_even'
        else:
            attr = 'messagesummary_odd'
        sumstr = self.__str__()
        txt = urwid.AttrMap(urwid.Text(sumstr), attr, 'messagesummary_focus')
        urwid.WidgetWrap.__init__(self, txt)

    def __str__(self):
        author, address = self.message.get_author()
        date = self.message.get_datestring()
        if date == None:
            rep = author
        else:
            rep = '%s (%s)' % (author, date)
        return rep

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageHeaderWidget(urwid.AttrMap):
    """
    displays a "key:value\n" list of email headers.
    RFC 2822 style encoded values are decoded into utf8 first.
    """

    def __init__(self, eml, displayed_headers=None, hidden_headers=None):
        """
        :param eml: the email
        :type eml: email.Message
        :param displayed_headers: a whitelist of header fields to display
        :type displayed_headers: list(str)
        :param hidden_headers: a blacklist of header fields to display
        :type hidden_headers: list(str)
        """
        self.eml = eml
        self.display_all = False
        self.displayed_headers = displayed_headers
        self.hidden_headers = hidden_headers
        headerlines = self._build_lines(displayed_headers, hidden_headers)
        urwid.AttrMap.__init__(self, urwid.Pile(headerlines), 'message_header')

    def toggle_all(self):
        if self.display_all:
            self.display_all = False
            headerlines = self._build_lines(self.displayed_headers,
                                            self.hidden_headers)
        else:
            self.display_all = True
            headerlines = self._build_lines(None, None)
        logging.info('all : %s' % headerlines)
        self.original_widget = urwid.Pile(headerlines)

    def _build_lines(self, displayed, hidden):
        max_key_len = 1
        headerlines = []
        if not displayed:
            displayed = self.eml.keys()
        if hidden:
            displayed = filter(lambda x: x not in hidden, displayed)
        #calc max length of key-string
        for key in displayed:
            if key in self.eml:
                if len(key) > max_key_len:
                    max_key_len = len(key)
        for key, value in self.eml.items():
            #todo: parse from,cc,bcc seperately into name-addr-widgets
            # TODO: check indexed keys for None and highlight as invalid
            if key in displayed:
                value = message.decode_header(value)
                keyw = ('fixed', max_key_len + 1,
                        urwid.Text(('message_header_key', key)))
                valuew = urwid.Text(('message_header_value', value))
                line = urwid.Columns([keyw, valuew])
                headerlines.append(line)
        return headerlines


class MessageBodyWidget(urwid.AttrMap):
    """displays printable parts of an email"""

    def __init__(self, msg):
        bodytxt = message.extract_body(msg)
        urwid.AttrMap.__init__(self, urwid.Text(bodytxt), 'message_body')


class AttachmentWidget(urwid.WidgetWrap):
    def __init__(self, attachment, selectable=True):
        self._selectable = selectable
        self.attachment = attachment
        if not isinstance(attachment, message.Attachment):
            self.attachment = message.Attachment(self.attachment)
        widget = urwid.AttrMap(urwid.Text(self.attachment.__str__()),
                               'message_attachment',
                               'message_attachment_focussed')
        urwid.WidgetWrap.__init__(self, widget)

    def get_attachment(self):
        return self.attachment

    def selectable(self):
        return self._selectable

    def keypress(self, size, key):
        return key
