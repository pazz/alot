# encoding=utf-8
from __future__ import absolute_import

import unittest

from alot.settings import checks


class TestForceList(unittest.TestCase):

    def test_strings_are_converted_to_single_item_lists(self):
        forced = checks.force_list('hello')
        self.assertEqual(forced, ['hello'])

    def test_empty_strings_are_converted_to_empty_lists(self):
        forced = checks.force_list('')
        self.assertEqual(forced, [])
