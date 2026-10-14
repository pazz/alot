# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

from alot.buffers import TagListBuffer


class TestTagListBuffer(unittest.TestCase):

    @mock.patch('alot.buffers.taglist.settings')
    @mock.patch('alot.widgets.globals.settings')
    def test_rebuild_keeps_the_selected_tag(self, settings, _):
        settings.get_tagstring_representation.side_effect = \
            lambda tag, *_: {'translated': tag, 'normal': None,
                             'focussed': None}
        buf = TagListBuffer(mock.Mock(), ['a', 'b'])
        buf.focus_last()
        buf.rebuild()
        self.assertEqual(buf.get_selected_tag(), 'b')
