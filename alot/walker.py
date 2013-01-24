# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import urwid
import logging
from alot.foreign.urwidtrees import Tree


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

    def __contains__(self, name):
        return self.lines.__contains__(name)

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


class ThreadTree(Tree):
    def __init__(self, thread):
        self._thread = thread
        self.root = thread.get_toplevel_messages()[0].get_message_id()
        self._parent_of = {}
        self._first_child_of = {}
        self._last_child_of = {}
        self._next_sibling_of = {}
        self._prev_sibling_of = {}
        self._message = {}

        for parent, childlist in thread.get_messages().items():
            pid = parent.get_message_id()
            self._message[pid] = parent

            if childlist:
                cid = childlist[0].get_message_id()
                self._first_child_of[pid] = cid
                self._parent_of[cid] = pid
                self._prev_sibling_of[cid] = None
                self._next_sibling_of[cid] = None

                last_cid = cid
                for child in childlist[1:]:
                    cid = child.get_message_id()
                    self._parent_of[cid] = pid
                    self._prev_sibling_of[cid] = last_cid
                    self._next_sibling_of[last_cid] = cid
                self._next_sibling_of[cid] = None

    def parent_position(self, pos):
        return self._parent_of[pos]

    def first_child_position(self, pos):
        return self._first_child_of[pos]

    def last_child_position(self, pos):
        return self._last_child_of[pos]

    def next_sibling_position(self, pos):
        return self._next_sibling_of(pos)

    def prev_sibling_position(self, pos):
        return self._prev_sibling_of(pos)
