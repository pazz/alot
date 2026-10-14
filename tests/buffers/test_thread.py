# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

import alot.commands.globals  # noqa: F401, render() refers to it
from alot.buffers import ThreadBuffer

from .. import utilities


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


class TestAutoRemoveUnread(unittest.TestCase):

    @mock.patch('alot.buffers.thread.settings.get', return_value=True)
    @utilities.async_test
    async def test_single_message_thread(self, _):
        """The cursor stays on the summary of the only, expanded message."""
        buf = ThreadBuffer.__new__(ThreadBuffer)
        buf.message_count = 1
        buf._auto_unread_dont_touch_mids = set()
        buf._auto_unread_writing = False
        buf.ui = utilities.make_ui(apply_command=mock.AsyncMock())
        buf.body = mock.Mock(**{'get_focus.return_value': (None, ('m', (0,)))})
        msg = mock.Mock(**{'get_tags.return_value': ['unread']})
        buf.get_selected_message = lambda: msg
        buf.render((80, 24))
        msg.remove_tags.assert_called_once_with(['unread'], afterwards=mock.ANY)
