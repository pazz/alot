# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
"""
Widgets specific to search mode
"""
import urwid

from ..settings.const import settings
from ..helper import shorten_author_string
from .utils import AttrFlipWidget
from .globals import TagWidget


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

        part_w = None
        width = None
        content = None
        if name == 'date':
            newest = None
            datestring = ''
            if self.thread:
                newest = self.thread.get_newest_date()
                if newest is not None:
                    datestring = settings.represent_datetime(newest)
            content = pad(datestring)
        elif name == 'mailcount':
            if self.thread:
                mailcountstring = "(%d)" % self.thread.get_total_messages()
            else:
                mailcountstring = "(?)"
            content = pad(mailcountstring)
        elif name == 'authors':
            if self.thread:
                authors = self.thread.get_authors_string() or '(None)'
            else:
                authors = '(None)'
            content = pad(authors, shorten_author_string)
        elif name == 'subject':
            if self.thread:
                subjectstring = self.thread.get_subject() or ' '
            else:
                subjectstring = ' '
            # sanitize subject string:
            subjectstring = subjectstring.replace('\n', ' ')
            subjectstring = subjectstring.replace('\r', '')
            content = pad(subjectstring)
        elif name == 'content':
            if self.thread:
                msgs = self.thread.get_messages().keys()
            else:
                msgs = []
            # sort the most recent messages first
            msgs.sort(key=lambda msg: msg.get_date(), reverse=True)
            lastcontent = ' '.join([m.get_text_content() for m in msgs])
            content = pad(lastcontent.replace('\n', ' ').strip())

        # define width and part_w in case the above produced a content string
        if content:
            text = urwid.Text(content, wrap='clip')
            width = text.pack()[0]
            part_w = AttrFlipWidget(text, struct[name])

        # the above dealt with plain text parts, which result in (wrapped)
        # urwid.Text widgets. Below we deal with the special case of taglist
        # parts, which are text in an urwid.Colums widget.

        if name == 'tags':
            if self.thread:
                fallback_normal = struct[name]['normal']
                fallback_focus = struct[name]['focus']
                tag_widgets = sorted(
                    TagWidget(t, fallback_normal, fallback_focus)
                    for t in self.thread.get_tags())
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
                part_w = urwid.Columns(cols, dividechars=1)
                width = length
        return width, part_w

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
