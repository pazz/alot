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

    def rebuild(self):
        self.thread = self.dbman.get_thread(self.tid)
        self.widgets = []
        columns = []
        self.structure = settings.get_threadline_theming(self.thread)

        # create a column for every part of the threadline
        for partname in self.structure['parts']:
            # extract min/max width, overall width, and alignment parameters
            minw = maxw = None
            width_tuple = self.structure[partname]['width']
            if width_tuple is not None:
                if width_tuple[0] == 'fit':
                    minw, maxw = width_tuple[1:]
            alignment = self.structure[partname]['alignment']

            # build widget(s) around this part's content and remember them so
            # that self.render() may change local attributes.
            if partname == 'tags':
                width, part = build_tags_part(self.thread.get_tags(),
                                              self.structure['tags']['normal'],
                                              self.structure['tags']['focus'])
                for w in part.widget_list:
                    self.widgets.append(w)
            else:
                width, part = build_text_part(partname, self.thread,
                                              self.structure[partname], minw,
                                              maxw, alignment)
                self.widgets.append(part)

            # combine width info and widget into an urwid.Column entry
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


def build_tags_part(tags, attr_normal, attr_focus):
    """
    create an urwid.Columns widget (wrapped in approproate Attributes)
    to display a list of tag strings, as part of a threadline.

    :param tags: list of tag strings to include
    :type tags: list of str
    :param attr_normal: urwid attribute to use if unfocussed
    :param attr_focus: urwid attribute to use if focussed
    :return: overall width in characters and a Columns widget.
    :rtype: tuple[int, urwid.Columns]
    """
    part_w = None
    width = None
    tag_widgets = []
    cols = []
    width = -1

    # create individual TagWidgets and sort them
    tag_widgets = [TagWidget(t, attr_normal, attr_focus) for t in tags]
    tag_widgets = sorted(tag_widgets)

    for tag_widget in tag_widgets:
        if not tag_widget.hidden:
            wrapped_tagwidget = tag_widget
            tag_width = tag_widget.width()
            cols.append(('fixed', tag_width, wrapped_tagwidget))
            width += tag_width + 1
    if cols:
        part_w = urwid.Columns(cols, dividechars=1)
    return width, part_w


def build_text_part(name, thread, struct, minw, maxw, align):
    """
    create an urwid.Text widget (wrapped in approproate Attributes)
    to display a plain text parts in a threadline.
    create an urwid.Columns widget (wrapped in approproate Attributes)
    to display a list of tag strings, as part of a threadline.

    :param name: id of part to build
    :type name: str
    :param thread: the thread to get local info for
    :type thread: :class:`alot.db.thread.Thread`
    :param struct: theming attributes for this part, as provided by
                   :class:`alot.settings.theme.Theme.get_threadline_theming`
    :type struct: dict
    :param minw: minimal width to use
    :type minw: int
    :param maxw: maximal width to use
    :type maxw: int
    :param align: alignment of content in displayed string, if shorter.
                  must be "left", "right", or "center".
    :type align: str
    :return: overall width (in characters) and a widget.
    :rtype: tuple[int, AttrFliwWidget]
    """

    # local string padding function
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
        if thread:
            newest = thread.get_newest_date()
            if newest is not None:
                datestring = settings.represent_datetime(newest)
        content = pad(datestring)
    elif name == 'mailcount':
        if thread:
            mailcountstring = "(%d)" % thread.get_total_messages()
        else:
            mailcountstring = "(?)"
        content = pad(mailcountstring)
    elif name == 'authors':
        if thread:
            authors = thread.get_authors_string() or '(None)'
        else:
            authors = '(None)'
        content = pad(authors, shorten_author_string)
    elif name == 'subject':
        if thread:
            subjectstring = thread.get_subject() or ' '
        else:
            subjectstring = ' '
        # sanitize subject string:
        subjectstring = subjectstring.replace('\n', ' ')
        subjectstring = subjectstring.replace('\r', '')
        content = pad(subjectstring)
    elif name == 'content':
        if thread:
            msgs = sorted(thread.get_messages().keys(), key=lambda msg:
                          msg.get_date(), reverse=True)
            lastcontent = ' '.join(m.get_text_content() for m in msgs)
            content = pad(lastcontent.replace('\n', ' ').strip())
        else:
            content = pad('')

    # define width and part_w in case the above produced a content string
    if content:
        text = urwid.Text(content, wrap='clip')
        width = text.pack()[0]
        part_w = AttrFlipWidget(text, struct)

    return width, part_w
