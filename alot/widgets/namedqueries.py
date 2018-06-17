# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""
Widgets specific to Namedqueries mode
"""
from __future__ import absolute_import

import urwid


class QuerylineWidget(urwid.Columns):
    def __init__(self, query, count, count_unread):
        self.query = query

        count_widget = urwid.Text('{0:>7} {1:7}'.\
                format(count, '({0})'.format(count_unread)))
        name_widget = urwid.Text(query)

        urwid.Columns.__init__(self, (count_widget, name_widget),
                               dividechars=1)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_query(self):
        return self.query
