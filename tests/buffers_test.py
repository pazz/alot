# encoding=utf-8
# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from __future__ import absolute_import

import unittest

from alot.buffers import SearchBuffer

class TestSearchBuffer(unittest.TestCase):
    def test_find_tags_in_query(self):
        tags = ['no_space', 'a space', 'more spaces ', 'still_no_space']
        query = ('tag:{} AND is:/reg *ex+/ OR tag:"{}" '
                 'AND is:"{}" AND is:{} OR tag:/more regex*/').format(*tags)

        expected = tags
        actual = SearchBuffer._get_tags_in_query(query)
        self.assertEqual(expected, actual)
