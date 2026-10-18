# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

from alot.buffers.search import SearchBuffer


class TestRefreshThreadline(unittest.TestCase):

    def test_match_all_search_keeps_matching_threads(self):
        # '(*) AND thread:...' matches only some of a thread's messages
        buf = SearchBuffer.__new__(SearchBuffer)
        buf.querystring = '*'
        buf.limit = 0
        buf.threadlist = mock.Mock()
        buf.dbman = mock.Mock(**{'count_messages.return_value': 1})
        threadline = mock.Mock(tid='42')
        buf.refresh_threadline(threadline)
        self.assertEqual(buf.dbman.count_messages.call_args_list[0],
                         mock.call('thread:42'))
        threadline.rebuild.assert_called_once_with()
