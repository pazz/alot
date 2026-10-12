# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

from alot.buffers import ThreadBuffer


class TestFocusMovement(unittest.TestCase):

    @staticmethod
    def _buffer(focus, **positions):
        """A ThreadBuffer whose tree returns `positions` for message 'm'."""
        buf = ThreadBuffer.__new__(ThreadBuffer)
        buf._tree = mock.Mock(**{
            name + '.return_value': pos for name, pos in positions.items()})
        buf.get_selected_mid = lambda: 'm'
        buf._sanitize_position = lambda pos: ('sane',) + pos
        buf.get_focus = lambda: (None, focus)
        buf.set_focus = mock.Mock()
        return buf

    def test_forward(self):
        for method, tree_method in [
                ('focus_parent', 'parent_position'),
                ('focus_first_reply', 'first_child_position'),
                ('focus_last_reply', 'last_child_position'),
                ('focus_next_sibling', 'next_sibling_position'),
                ('focus_next', 'next_position')]:
            with self.subTest(method=method):
                buf = self._buffer(None, **{tree_method: 'n'})
                getattr(buf, method)()
                buf.set_focus.assert_called_once_with(('sane', 'n'))
                buf = self._buffer(None, **{tree_method: None})
                getattr(buf, method)()
                buf.set_focus.assert_not_called()

    def test_backward(self):
        for method, tree_method in [
                ('focus_prev_sibling', 'prev_sibling_position'),
                ('focus_prev', 'prev_position')]:
            with self.subTest(method=method):
                # focus inside the message: go to its start first
                buf = self._buffer('elsewhere', **{tree_method: 'p'})
                getattr(buf, method)()
                buf.set_focus.assert_called_once_with(('sane', 'm'))
                # focus at its start: move to the previous message
                buf = self._buffer(('sane', 'm'), **{tree_method: 'p'})
                getattr(buf, method)()
                buf.set_focus.assert_called_once_with(('sane', 'p'))
                buf = self._buffer(('sane', 'm'), **{tree_method: None})
                getattr(buf, method)()
                buf.set_focus.assert_not_called()
