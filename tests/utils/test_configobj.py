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


class TestWidthTuple(unittest.TestCase):

    def test_validates_width_tuple(self):
        with self.assertRaises(VdtTypeError):
            checks.width_tuple('invalid-value')

    def test_validates_width_tuple_for_fit_requires_two_args(self):
        with self.assertRaises(VdtTypeError):
            checks.width_tuple(['fit', 123])

    def test_args_for_fit_must_be_numbers(self):
        with self.assertRaises(VdtValueError):
            checks.width_tuple(['fit', 123, 'not-a-number'])

    def test_fit_with_two_numbers(self):
        fit_result = checks.width_tuple(['fit', 123, 456])
        self.assertEqual(('fit', 123, 456), fit_result)

    def test_validates_width_tuple_for_weight_needs_an_argument(self):
        with self.assertRaises(VdtTypeError):
            checks.width_tuple(['weight'])

    def test_arg_for_weight_must_be_a_number(self):
        with self.assertRaises(VdtValueError):
            checks.width_tuple(['weight', 'not-a-number'])

    def test_weight_with_a_number(self):
        weight_result = checks.width_tuple(['weight', 123])
        self.assertEqual(('weight', 123), weight_result)

    def test_validates_width_tuple_for_wrap_requires_four_args(self):
        with self.assertRaises(VdtTypeError):
            checks.width_tuple(['wrap', 123, 456, 789])

    def test_validates_width_tuple_for_wrap_must_be_numbers(self):
        with self.assertRaises(VdtValueError):
            checks.width_tuple(['wrap', 12, 34, 56, 'not-a-number'])

    def test_wrap_with_four_numbers(self):
        fit_result = checks.width_tuple(['wrap', 12, 34, 56, 78])
        self.assertEqual(('wrap', 12, 34, 56, 78), fit_result)
