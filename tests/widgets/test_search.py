# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

from alot.widgets import search


class TestPrepareDateString(unittest.TestCase):

    def test_thread_without_date(self):
        thread = mock.Mock(**{'get_newest_date.return_value': None})
        self.assertEqual(search.prepare_date_string(thread), ' ')
