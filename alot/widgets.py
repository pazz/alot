# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import urwid
import logging

from settings import settings
from alot.helper import shorten_author_string
from alot.helper import tag_cmp
from alot.helper import string_decode
import alot.db.message as message
from alot.db.attachment import Attachment
import time
from alot.db.utils import decode_header
from alot.settings.utils import resolve_att


class AttrFlipWidget(urwid.AttrMap):
    """
    An AttrMap that can remember attributes to set
    """
    def __init__(self, w, maps, init_map='normal'):
        self.maps = maps
        urwid.AttrMap.__init__(self, w, maps[init_map])

    def set_map(self, attrstring):
        self.set_attr_map({None: self.maps[attrstring]})


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
    """
    selectable line widget that represents a :class:`~alot.db.Thread`
    in the :class:`~alot.buffers.SearchBuffer`.

    Respected settings:
        * `general.display_content_in_threadline`
        * `general.timestamp_format`
    Theme settings:
        * `search_thread, search_thread_focus`
        * `search_thread_date, search_thread_date_focus`
        * `search_thread_mailcount, search_thread_mailcount_focus`
        * `search_thread_authors, search_thread_authors_focus`
        * `search_thread_subject, search_thread_subject_focus`
        * `search_thread_content, search_thread_content_focus`
    """
    # The pretty_datetime needs 9 characters, but only 8 if locale
    # doesn't use am/pm (in which case "jan 2012" is the longest)
    pretty_datetime_len = 8 if len(time.strftime("%P")) == 0 else 9

    def __init__(self, tid, dbman):
        self.dbman = dbman
        self.thread = dbman.get_thread(tid)
        self.tag_widgets = []
        self.display_content = settings.get('display_content_in_threadline')
        self.structure = None
        self.rebuild()
        normal = self.structure['normal']
        focussed = self.structure['focus']
        urwid.AttrMap.__init__(self, self.columns, normal, focussed)

    def _build_part(self, name, struct, minw, maxw, align):
        def pad(string, shorten=None):
            if maxw:
                if len(string) > maxw:
                    if shorten:
                        string = shorten(string, maxw)
                    else:
                        string = string[:maxw]
            if minw:
                if len(string) < minw:
                    if align == 'left':
                        string = string.ljust(minw)
                    elif align == 'center':
                        string = string.center(minw)
                    else:
                        string = string.rjust(minw)
            return string

        part = None
        width = None
        if name == 'date':
            newest = None
            datestring = ''
            if self.thread:
                newest = self.thread.get_newest_date()
                datestring = settings.represent_datetime(newest)
                datestring = datestring.rjust(self.pretty_datetime_len)
            datestring = pad(datestring)
            width = len(datestring)
            part = AttrFlipWidget(urwid.Text(datestring), struct['date'])

        elif name == 'mailcount':
            if self.thread:
                mailcountstring = "(%d)" % self.thread.get_total_messages()
            else:
                mailcountstring = "(?)"
            datestring = pad(mailcountstring)
            width = len(mailcountstring)
            mailcount_w = AttrFlipWidget(urwid.Text(mailcountstring),
                                             struct['mailcount'])
            part = mailcount_w
        elif name == 'authors':
            if self.thread:
                authors = self.thread.get_authors_string() or '(None)'
            else:
                authors = '(None)'
            authorsstring = pad(authors, shorten_author_string)
            authors_w = AttrFlipWidget(urwid.Text(authorsstring),
                                           struct['authors'])
            width = len(authorsstring)
            part = authors_w

        elif name == 'subject':
            if self.thread:
                subjectstring = self.thread.get_subject() or ''
            else:
                subjectstring = ''
            # sanitize subject string:
            subjectstring = subjectstring.replace('\n', ' ')
            subjectstring = subjectstring.replace('\r', '')
            subjectstring = pad(subjectstring.strip())

            subject_w = AttrFlipWidget(urwid.Text(subjectstring, wrap='clip'),
                                           struct['subject'])
            if subjectstring:
                width = len(subjectstring)
                part = subject_w

        elif name == 'content':
            if self.thread:
                msgs = self.thread.get_messages().keys()
            else:
                msgs = []
            # sort the most recent messages first
            msgs.sort(key=lambda msg: msg.get_date(), reverse=True)
            lastcontent = ' '.join([m.get_text_content() for m in msgs])
            contentstring = pad(lastcontent.replace('\n', ' ').strip())
            content_w = AttrFlipWidget(urwid.Text(
                                                   contentstring,
                                                   wrap='clip'),
                                                   struct['content'])
            width = len(contentstring)
            part = content_w
        elif name == 'tags':
            if self.thread:
                fallback_normal = struct[name]['normal']
                fallback_focus = struct[name]['focus']
                tag_widgets = [TagWidget(t, fallback_normal, fallback_focus)
                                    for t in self.thread.get_tags()]
                tag_widgets.sort(tag_cmp,
                                  lambda tag_widget: tag_widget.translated)
            else:
                tag_widgets = []
            cols = []
            length = -1
            for tag_widget in tag_widgets:
                if not tag_widget.hidden:
                    wrapped_tagwidget = tag_widget
                    tag_width = tag_widget.width()
                    cols.append(('fixed', tag_width, wrapped_tagwidget))
                    length += tag_width + 1
            if cols:
                part = urwid.Columns(cols, dividechars=1)
                width = length
        return width, part

    def rebuild(self):
        self.widgets = []
        columns = []
        self.structure = settings.get_threadline_theming(self.thread)
        for partname in self.structure['parts']:
            minw = maxw = None
            width_tuple = self.structure[partname]['width']
            if width_tuple is not None:
                if width_tuple[0] == 'fit':
                    minw, maxw = width_tuple[1:]
            align_mode = self.structure[partname]['alignment']
            width, part = self._build_part(partname, self.structure,
                                           minw, maxw, align_mode)
            if part is not None:
                if isinstance(part, urwid.Columns):
                    for w in part.widget_list:
                        self.widgets.append(w)
                else:
                    self.widgets.append(part)

                # compute width and align
                if width_tuple[0] == 'weight':
                    columnentry = width_tuple + (part,)
                else:
                    columnentry = ('fixed', width, part)
                columns.append(columnentry)
        self.columns = urwid.Columns(columns, dividechars=1)
        self.original_widget = self.columns

    def render(self, size, focus=False):
        for w in self.widgets:
            w.set_map('focus' if focus else 'normal')
        return urwid.AttrMap.render(self, size, focus)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_thread(self):
        return self.thread

    def _get_theme(self, component, focus=False):
        path = ['search', 'threadline', component]
        if focus:
            path.append('focus')
        else:
            path.append('normal')
        return settings.get_theming_attribute(path)


class BufferlineWidget(urwid.Text):
    """
    selectable text widget that represents a :class:`~alot.buffers.Buffer`
    in the :class:`~alot.buffers.BufferlistBuffer`.
    """

    def __init__(self, buffer):
        self.buffer = buffer
        line = buffer.__str__()
        urwid.Text.__init__(self, line, wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_buffer(self):
        return self.buffer


class TagWidget(urwid.AttrMap):
    """
    text widget that renders a tagstring.

    It looks up the string it displays in the `tag-translate` section
    of the config as well as custom theme settings for its tag. The
    tag may also be configured as hidden, which users of this widget
    should honour.
    """
    def __init__(self, tag, fallback_normal=None, fallback_focus=None):
        self.tag = tag
        representation = settings.get_tagstring_representation(tag,
                                                               fallback_normal,
                                                               fallback_focus)
        self.translated = representation['translated']
        self.hidden = self.translated == ''
        self.txt = urwid.Text(self.translated, wrap='clip')
        normal_att = representation['normal']
        focus_att = representation['focussed']
        self.attmaps = {'normal': normal_att, 'focus': focus_att}
        urwid.AttrMap.__init__(self, self.txt, normal_att, focus_att)

    def set_map(self, attrstring):
        self.set_attr_map({None: self.attmaps[attrstring]})

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
        self.set_attr_map(self.attmap['focus'])

    def set_unfocussed(self):
        self.set_attr_map(self.attmap['normal'])


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
        elif key == 'ctrl a':
            self.set_edit_pos(0)
        elif key == 'ctrl e':
            self.set_edit_pos(len(self.edit_text))
        else:
            result = urwid.Edit.keypress(self, size, key)
            self.completions = None
            return result


class MessageWidget(urwid.WidgetWrap):
    """
    Flow widget that renders a :class:`~alot.db.message.Message`.

    Respected settings:
        * `general.displayed_headers`
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
        self._filtered_headers = [k for k in displayed if k in self.mail]
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
            if key in mail:
                if key.lower() in ['cc', 'bcc', 'to']:
                    values = mail.get_all(key)
                    values = [decode_header(v, normalize=norm) for v in values]
                    lines.append((key, ', '.join(values)))
                else:
                    for value in mail.get_all(key):
                        dvalue = decode_header(value, normalize=norm)
                        lines.append((key, dvalue))

        key_att = settings.get_theming_attribute('thread', 'header_key')
        value_att = settings.get_theming_attribute('thread', 'header_value')
        cols = [HeadersList(lines, key_att, value_att)]
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

    Theme settings:
        * `thread_summary_even`
        * `thread_summary_odd`
        * `thread_summary_focus`
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
        focus_att = settings.get_theming_attribute('thread', 'summary', 'focus')
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
        if date != None:
            rep += " (%s)" % date
        return rep

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class HeadersList(urwid.WidgetWrap):
    """ renders a pile of header values as key/value list """
    def __init__(self, headerslist, key_attr, value_attr):
        self.headers = headerslist
        self.key_attr = key_attr
        self.value_attr = value_attr
        pile = urwid.Pile(self._build_lines(headerslist))
        att = settings.get_theming_attribute('thread', 'header')
        pile = urwid.AttrMap(pile, att)
        urwid.WidgetWrap.__init__(self, pile)

    def __str__(self):
        return str(self.headers)

    def _build_lines(self, lines):
        max_key_len = 1
        headerlines = []
        #calc max length of key-string
        for key, value in lines:
            if len(key) > max_key_len:
                max_key_len = len(key)
        for key, value in lines:
            ##todo : even/odd
            keyw = ('fixed', max_key_len + 1,
                    urwid.Text((self.key_attr, key)))
            valuew = urwid.Text((self.value_attr, value))
            line = urwid.Columns([keyw, valuew])
            headerlines.append(line)
        return headerlines


class MessageBodyWidget(urwid.AttrMap):
    """
    displays printable parts of an email

    Theme settings:
        * `thread_body`
    """

    def __init__(self, msg):
        bodytxt = message.extract_body(msg)
        att = settings.get_theming_attribute('thread', 'body')
        urwid.AttrMap.__init__(self, urwid.Text(bodytxt), att)


class AttachmentWidget(urwid.WidgetWrap):
    """
    one-line summary of an :class:`~alot.db.attachment.Attachment`.

    Theme settings:
        * `thread_attachment`
        * `thread_attachment_focus`
    """
    def __init__(self, attachment, selectable=True):
        self._selectable = selectable
        self.attachment = attachment
        if not isinstance(attachment, Attachment):
            self.attachment = Attachment(self.attachment)
        att = settings.get_theming_attribute('thread', 'attachment')
        focus_att = settings.get_theming_attribute('thread',
                                                   'attachment_focus')
        widget = urwid.AttrMap(urwid.Text(self.attachment.__str__()),
                               att, focus_att)
        urwid.WidgetWrap.__init__(self, widget)

    def get_attachment(self):
        return self.attachment

    def selectable(self):
        return self._selectable

    def keypress(self, size, key):
        return key
