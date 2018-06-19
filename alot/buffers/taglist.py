# Copyright (C) 2011-2018  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import urwid

from .buffer import Buffer
from ..settings.const import settings
from ..widgets.globals import TagWidget


class TagListBuffer(Buffer):
    """lists all tagstrings present in the notmuch database"""

    modename = 'taglist'

    def __init__(self, ui, alltags=None, filtfun=lambda x: x):
        self.filtfun = filtfun
        self.ui = ui
        self.tags = alltags or []
        self.isinitialized = False
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

    def rebuild(self):
        if self.isinitialized:
            focusposition = self.taglist.get_focus()[1]
        else:
            focusposition = 0
            self.isinitialized = True

        lines = list()
        displayedtags = sorted((t for t in self.tags if self.filtfun(t)),
                               key=str.lower)
        for (num, b) in enumerate(displayedtags):
            if (num % 2) == 0:
                attr = settings.get_theming_attribute('taglist', 'line_even')
            else:
                attr = settings.get_theming_attribute('taglist', 'line_odd')
            focus_att = settings.get_theming_attribute('taglist', 'line_focus')

            tw = TagWidget(b, attr, focus_att)
            rows = [('fixed', tw.width(), tw)]
            if tw.hidden:
                rows.append(urwid.Text(b + ' [hidden]'))
            elif tw.translated is not b:
                rows.append(urwid.Text('(%s)' % b))
            line = urwid.Columns(rows, dividechars=1)
            line = urwid.AttrMap(line, attr, focus_att)
            lines.append(line)

        self.taglist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.body = self.taglist

        self.taglist.set_focus(focusposition % len(displayedtags))

    def focus_first(self):
        """Focus the first line in the tag list."""
        self.body.set_focus(0)

    def focus_last(self):
        allpos = self.taglist.body.positions(reverse=True)
        if allpos:
            lastpos = allpos[0]
            self.body.set_focus(lastpos)

    def get_selected_tag(self):
        """returns selected tagstring"""
        cols, _ = self.taglist.get_focus()
        tagwidget = cols.original_widget.get_focus()
        return tagwidget.tag
