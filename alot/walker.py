# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import logging
import urwid


class IterableWalker(urwid.ListWalker):

    """An urwid walker for iterables.

    Works like ListWalker, except it takes an iterable object instead of a
    concrete type. This allows for lazy operations of very large sequences of
    data, such as a sequences of threads with certain notmuch tags.

    :param iterable: An iterator of objects to walk over
    :type iterable: Iterable[T]
    :param containerclass: An urwid widget to wrap each object in
    :type containerclass: urwid.Widget
    :param reverse: Reverse the order of the iterable
    :type reverse: bool
    :param **kwargs: Forwarded to container class.
    """

    def __init__(self, iterable, containerclass, reverse=False, **kwargs):
        self.iterable = iterable
        self.kwargs = kwargs
        self.containerclass = containerclass
        self.lines = []
        self.focus = 0
        self.empty = False
        self.direction = -1 if reverse else 1

    def __contains__(self, name):
        return self.lines.__contains__(name)

    def get_focus(self):
        return self._get_at_pos(self.focus)

    def set_focus(self, focus):
        self.focus = focus
        self._modified()

    def get_next(self, start_from):
        return self._get_at_pos(start_from + self.direction)

    def get_prev(self, start_from):
        return self._get_at_pos(start_from - self.direction)

    def remove(self, obj):
        next_focus = self.focus % len(self.lines)
        if self.focus == len(self.lines) - 1 and self.empty:
            next_focus = self.focus - 1

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
            next_obj = next(self.iterable)
            next_widget = self.containerclass(next_obj, **self.kwargs)
            self.lines.append(next_widget)
        except StopIteration:
            logging.debug('EMPTY PIPE')
            next_widget = None
            self.empty = True
        return next_widget

    def get_lines(self):
        return self.lines
