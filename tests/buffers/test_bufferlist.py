# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

from alot.buffers import BufferlistBuffer


class TestBufferlistBuffer(unittest.TestCase):

    @mock.patch('alot.buffers.bufferlist.settings')
    def test_rebuild_keeps_the_selected_buffer(self, _):
        ui = mock.Mock(buffers=[mock.Mock(), mock.Mock()])
        buf = BufferlistBuffer(ui)
        buf.body.set_focus(1)
        buf.rebuild()
        self.assertIs(buf.get_selected_buffer(), ui.buffers[1])
