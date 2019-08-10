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
        self.structure = settings.get_threadline_theming(self.thread)

        columns = []

        # combine width info and widget into an urwid.Column entry
        def add_column(width, part):
            width_tuple = self.structure[partname]['width']
            if width_tuple[0] == 'weight':
                columnentry = width_tuple + (part,)
            else:
                columnentry = ('fixed', width, part)
            columns.append(columnentry)

        # create a column for every part of the threadline
        for partname in self.structure['parts']:
            # build widget(s) around this part's content and remember them so
            # that self.render() may change local attributes.
            if partname == 'tags':
                width, part = build_tags_part(self.thread.get_tags(),
                                              self.structure['tags']['normal'],
                                              self.structure['tags']['focus'])
                if part:
                    add_column(width, part)
                    for w in part.widget_list:
                        self.widgets.append(w)
            else:
                width, part = build_text_part(partname, self.thread,
                                              self.structure[partname])
                add_column(width, part)
                self.widgets.append(part)

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


def build_text_part(name, thread, struct):
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
    :return: overall width (in characters) and a widget.
    :rtype: tuple[int, AttrFliwWidget]
    """

    part_w = None
    width = None

    # extract min and max allowed width from theme
    minw = 0
    maxw = None
    width_tuple = struct['width']
    if width_tuple is not None:
        if width_tuple[0] == 'fit':
            minw, maxw = width_tuple[1:]

    content = prepare_string(name, thread, maxw)

    # pad content if not long enough
    if minw:
        alignment = struct['alignment']
        if alignment == 'left':
            content = content.ljust(minw)
        elif alignment == 'center':
            content = content.center(minw)
        else:
            content = content.rjust(minw)

    # define width and part_w
    text = urwid.Text(content, wrap='clip')
    width = text.pack((maxw or minw,))[0]
    part_w = AttrFlipWidget(text, struct)

    return width, part_w


def prepare_date_string(thread):
    newest = None
    newest = thread.get_newest_date()
    if newest is not None:
        datestring = settings.represent_datetime(newest)
    return datestring


def prepare_mailcount_string(thread):
    return "(%d)" % thread.get_total_messages()


def prepare_authors_string(thread):
    return thread.get_authors_string() or '(None)'


def prepare_subject_string(thread):
    return thread.get_subject() or ' '


def prepare_content_string(thread):
    msgs = sorted(thread.get_messages().keys(),
                  key=lambda msg: msg.get_date(), reverse=True)
    lastcontent = ' '.join(m.get_body_text() for m in msgs)
    lastcontent = lastcontent.replace('^>.*$', '')
    return lastcontent


def prepare_string(partname, thread, maxw):
    """
    extract a content string for part 'partname' from 'thread' of maximal
    length 'maxw'.
    """
    # map part names to function extracting content string and custom shortener
    prep = {
        'mailcount': (prepare_mailcount_string, None),
        'date': (prepare_date_string, None),
        'authors': (prepare_authors_string, shorten_author_string),
        'subject': (prepare_subject_string, None),
        'content': (prepare_content_string, None),
    }

    s = ' '  # fallback value
    if thread:
        # get extractor and shortener
        content, shortener = prep[partname]

        # get string
        s = content(thread)

    # sanitize
    s = s.replace('\n', ' ')
    s = s.replace('\r', '')

    # shorten if max width is requested
    if maxw:
        if len(s) > maxw and shortener:
            s = shortener(s, maxw)
        else:
            s = s[:maxw]
    return s
