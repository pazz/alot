"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
import urwid


class PipeWalker(urwid.ListWalker):
    """urwid.ListWalker that reads next items from a pipe and
    wraps them in `containerclass` widgets for displaying
    """
    def __init__(self, pipe, containerclass, **kwargs):
        self.pipe = pipe
        self.kwargs = kwargs
        self.containerclass = containerclass
        self.lines = []
        self.focus = 0
        self.empty = False

    def get_focus(self):
        return self._get_at_pos(self.focus)

    def set_focus(self, focus):
        self.focus = focus
        self._modified()

    def get_next(self, start_from):
        return self._get_at_pos(start_from + 1)

    def get_prev(self, start_from):
        return self._get_at_pos(start_from - 1)

    def remove(self, obj):
        self.lines.remove(obj)
        if self.lines:
            self.set_focus(self.focus % len(self.lines))
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
            next_obj = self.pipe.recv()
            next_widget = self.containerclass(next_obj, **self.kwargs)
            self.lines.append(next_widget)
        except EOFError:
            next_widget = None
            self.empty = True
        return next_widget

    def get_lines(self):
        return self.lines
