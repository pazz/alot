# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import logging
import urwid


class PipeWalker(urwid.ListWalker):
    """urwid.ListWalker that reads next items from a pipe and
    wraps them in `containerclass` widgets for displaying
    """
    def __init__(self, pipe, containerclass, reverse=False, **kwargs):
        self.pipe = pipe
        self.kwargs = kwargs
        self.containerclass = containerclass
        self.lines = []
        self._focus = 0
        self.empty = False
        self.direction = -1 if reverse else 1

    def __contains__(self, name):
        return self.lines.__contains__(name)

    @property
    def focus(self):
        return self._get_at_pos(self._focus)

    @focus.setter
    def focus(self, value):
        self._focus = value
        self._modified()

    def get_next(self, start_from):
        return self._get_at_pos(start_from + self.direction)

    def get_prev(self, start_from):
        return self._get_at_pos(start_from - self.direction)

    def remove(self, obj):
        next_focus = self._focus % len(self.lines)
        if self._focus == len(self.lines) - 1 and self.empty:
            next_focus = self._focus - 1

        self.lines.remove(obj)
        if self.lines:
            self.set_focus(next_focus)
        self._modified()

    def _get_at_pos(self, pos):
        if pos < 0:  # pos too low
            return (None, None)
        elif pos > len(self.lines):  # pos too high
            return (None, None)
        elif len(self.lines) > pos:  # pos already cached
            return (self.lines[pos], pos)
        else:  # pos not cached yet, look at next item from iterator
            if self.empty:  # iterator is empty
                return (None, None)
            else:
                widget = self._get_next_item()
                if widget:
                    return (widget, pos)
                else:
                    return (None, None)

    def _get_next_item(self):
        if self.empty:
            return None
        try:
            # the next line blocks until it can read from the pipe or
            # EOFError is raised. No races here.
            next_obj = self.pipe.recv()
            next_widget = self.containerclass(next_obj, **self.kwargs)
            self.lines.append(next_widget)
        except EOFError:
            logging.debug('EMPTY PIPE')
            next_widget = None
            self.empty = True
        return next_widget

    def get_lines(self):
        return self.lines
