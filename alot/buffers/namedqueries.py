# Copyright (C) 2011-2018  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import urwid

from .buffer import Buffer
from ..settings.const import settings
from ..widgets.namedqueries import QuerylineWidget


class NamedQueriesBuffer(Buffer):
    """lists named queries present in the notmuch database"""

    modename = 'namedqueries'

    def __init__(self, ui, filtfun):
        self.ui = ui
        self.filtfun = filtfun
        self.isinitialized = False
        self.querylist = None
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

    def rebuild(self):
        self.queries = self.ui.dbman.get_named_queries()

        if self.isinitialized:
            focusposition = self.querylist.get_focus()[1]
        else:
            focusposition = 0

        lines = []
        for (num, key) in enumerate(self.queries):
            value = self.queries[key]
            count = self.ui.dbman.count_messages('query:"%s"' % key)
            count_unread = self.ui.dbman.count_messages('query:"%s" and '
                                                        'tag:unread' % key)
            line = QuerylineWidget(key, value, count, count_unread)

            if (num % 2) == 0:
                attr = settings.get_theming_attribute('namedqueries',
                                                      'line_even')
            else:
                attr = settings.get_theming_attribute('namedqueries',
                                                      'line_odd')
            focus_att = settings.get_theming_attribute('namedqueries',
                                                       'line_focus')

            line = urwid.AttrMap(line, attr, focus_att)
            lines.append(line)

        self.querylist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.body = self.querylist

        self.querylist.set_focus(focusposition % len(self.queries))

        self.isinitialized = True

    def focus_first(self):
        """Focus the first line in the query list."""
        self.body.set_focus(0)

    def focus_last(self):
        allpos = self.querylist.body.positions(reverse=True)
        if allpos:
            lastpos = allpos[0]
            self.body.set_focus(lastpos)

    def get_selected_query(self):
        """returns selected query"""
        return self.querylist.get_focus()[0].original_widget.query

    def get_info(self):
        info = {}

        info['query_count'] = len(self.queries)

        return info
