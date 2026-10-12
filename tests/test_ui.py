# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

import urwid

from alot.ui import UI

from . import utilities


@mock.patch('alot.ui.settings.get', mock.Mock(return_value=': '))
@mock.patch('alot.ui.settings.get_theming_attribute', mock.Mock())
class TestOverlayInput(unittest.TestCase):

    def _ui(self):
        ui = UI.__new__(UI)
        ui.mainloop = mock.Mock(widget=urwid.SolidFill())
        ui._passall = False
        return ui

    def _answer(self, ui, fut, key):
        root = ui.mainloop.widget.bottom_w
        self.assertTrue(ui._passall)
        ui.mainloop.widget.top_w.keypress((80,), key)
        self.assertIs(ui.mainloop.widget, root)
        self.assertFalse(ui._passall)
        return fut.result()

    @utilities.async_test
    async def test_prompt(self):
        ui = self._ui()
        fut = ui.prompt('question', text='answer')
        self.assertEqual(self._answer(ui, fut, 'enter'), 'answer')

    @utilities.async_test
    async def test_choice(self):
        ui = self._ui()
        fut = ui.choice('question')
        self.assertEqual(self._answer(ui, fut, 'y'), 'yes')
