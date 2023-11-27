# encoding=utf-8
import unittest

from alot.utils import configobj as checks
from validate import VdtTypeError, VdtValueError

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

    def test_validates_width_tuple(self):
        with self.assertRaises(VdtTypeError):
            checks.width_tuple('invalid-value')

    def test_validates_width_tuple_for_fit(self):
        with self.assertRaises(VdtTypeError):
            checks.width_tuple(['fit', 123])
        with self.assertRaises(VdtValueError):
            checks.width_tuple(['fit', 123, 'not-a-number'])
        fit_result = checks.width_tuple(['fit', 123, 456])
        self.assertEqual(('fit', 123, 456), fit_result)

    def test_validates_width_tuple_for_weight(self):
        with self.assertRaises(VdtTypeError):
            checks.width_tuple(['weight'])
        with self.assertRaises(VdtValueError):
            checks.width_tuple(['weight', 'not-a-number'])
        weight_result = checks.width_tuple(['weight', 123])
        self.assertEqual(('weight', 123), weight_result)
