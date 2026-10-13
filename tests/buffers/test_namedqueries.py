# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

from alot.buffers import NamedQueriesBuffer


class TestNamedQueriesBuffer(unittest.TestCase):

    @mock.patch('alot.buffers.namedqueries.settings')
    def test_no_queries(self, _):
        ui = mock.Mock()
        ui.dbman.get_named_queries.return_value = {}
        buf = NamedQueriesBuffer(ui)
        ui.dbman.get_named_queries.return_value = {'q': 'tag:inbox'}
        ui.dbman.count_messages.return_value = 0
        buf.rebuild()  # the first query appears
        self.assertEqual(buf.get_selected_query(), 'q')
