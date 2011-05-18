import urwid
import logging
from cnotmuch.notmuch import NotmuchError, STATUS

class IteratorWalker(urwid.ListWalker):

    def __init__(self, it, containerclass):
        self.it = it
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

    def _get_at_pos(self, pos):
        if pos < 0:
            return None, None

        if self.empty:
            return None, None
        if len(self.lines) > pos:
            return self.lines[pos], pos

        assert pos == len(self.lines), "out of order request?"

        widget = self._get_next_item()
        if widget:
            return widget, pos
        else:
            return None, None

    def _get_next_item(self):
        try:
            next_obj = self.it.next()
            next_widget = self.containerclass(next_obj)
            self.lines.append(next_widget)
        except StopIteration:
            next_widget = None
            self.empty = True
        return next_widget

class NotmuchIteratorWalker(IteratorWalker):
    def _get_next_item(self):
        logging.error("it still there")
        try:
            next_obj = self.it.next()
            logging.error("next obj: %s"%next_obj)
            next_widget = self.containerclass(next_obj)
            self.lines.append(next_widget)
        except NotmuchError:
            next_widget = None
        return next_widget
