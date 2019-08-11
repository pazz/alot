# Copyright (C) 2011-2018  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""
Widgets specific to Namedqueries mode
"""
import urwid


class QuerylineWidget(urwid.Columns):
    def __init__(self, key, value, count, count_unread):
        self.query = key

        count_widget = urwid.Text('{0:>7} {1:7}'.
                                  format(count, '({0})'.format(count_unread)))
        key_widget = urwid.Text(key)
        value_widget = urwid.Text(value)

        urwid.Columns.__init__(self, (key_widget, count_widget, value_widget),
                               dividechars=1)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_query(self):
        return self.query
