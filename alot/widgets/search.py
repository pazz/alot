# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
"""
Widgets specific to search mode
"""
import urwid

from alot.settings import settings
from alot.helper import shorten_author_string
from alot.helper import tag_cmp
from alot.widgets.utils import AttrFlipWidget
from alot.widgets.globals import TagWidget


class ThreadlineWidget(urwid.AttrMap):
    """
    selectable line widget that represents a :class:`~alot.db.Thread`
    in the :class:`~alot.buffers.SearchBuffer`.
    """
    def __init__(self, tid, dbman):
        self.dbman = dbman
        self.tid = tid
        self.thread = None  # will be set by refresh()
        self.tag_widgets = []
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
                if newest != None:
                    datestring = settings.represent_datetime(newest)
            datestring = pad(datestring)
            width = len(datestring)
            part = AttrFlipWidget(urwid.Text(datestring), struct['date'])

        elif name == 'mailcount':
            if self.thread:
                mailcountstring = "(%d)" % self.thread.get_total_messages()
            else:
                mailcountstring = "(?)"
            mailcountstring = pad(mailcountstring)
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
                subjectstring = self.thread.get_subject() or ' '
            else:
                subjectstring = ' '
            # sanitize subject string:
            subjectstring = subjectstring.replace('\n', ' ')
            subjectstring = subjectstring.replace('\r', '')
            subjectstring = pad(subjectstring)

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
            content_w = AttrFlipWidget(urwid.Text(contentstring, wrap='clip'),
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
        self.thread = self.dbman.get_thread(self.tid)
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
