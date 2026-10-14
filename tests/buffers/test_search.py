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


class TestRestoreFocus(unittest.TestCase):

    def test_no_widgets_for_a_thread_that_left_the_results(self):
        built = []

        def threadline(tid, dbman):
            built.append(tid)
            return mock.Mock(**{'get_thread.return_value.get_thread_id'
                                '.return_value': tid})

        buf = SearchBuffer.__new__(SearchBuffer)
        buf.dbman = mock.Mock(**{'get_threads.return_value': (
            iter(['t%d' % i for i in range(50)]), 50)})
        buf.querystring, buf.sort_order, buf.limit = 'tag:inbox', None, None
        buf.search_threads_rebuild_limit = 1000
        buf.threadlist = True
        buf.get_selected_thread = mock.Mock(
            **{'return_value.get_thread_id.return_value': 'archived'})
        with mock.patch('alot.buffers.search.ThreadlineWidget', threadline), \
                mock.patch('alot.buffers.search.urwid.ListBox'):
            buf.rebuild()
        # the focused thread was e.g. archived: nothing to look for
        self.assertEqual(built, [])
