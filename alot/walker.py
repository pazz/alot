import urwid
import logging


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
