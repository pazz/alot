# encoding=utf-8
import unittest

from alot.utils import configobj as checks

# Good descriptive test names often don't fit PEP8, which is meant to cover
# functions meant to be called by humans.
# pylint: disable=invalid-name


class TestForceList(unittest.TestCase):

    def test_strings_are_converted_to_single_item_lists(self):
        forced = checks.force_list('hello')
        self.assertEqual(forced, ['hello'])

    def test_empty_strings_are_converted_to_empty_lists(self):
        forced = checks.force_list('')
        self.assertEqual(forced, [])
