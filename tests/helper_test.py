# encoding=utf-8

"""Test suite for alot.helper module."""
from __future__ import absolute_import

import unittest

from alot import helper


class TestHelperShortenAuthorString(unittest.TestCase):

    authors = u'King Kong, Mucho Muchacho, Jaime Huerta, Flash Gordon'

    def test_high_maxlength_keeps_string_intact(self):
        short = helper.shorten_author_string(self.authors, 60)
        self.assertEqual(short, self.authors)

    def test_shows_only_first_names_if_they_fit(self):
        short = helper.shorten_author_string(self.authors, 40)
        self.assertEqual(short, u"King, Mucho, Jaime, Flash")

    def test_adds_ellipses_to_long_first_names(self):
        short = helper.shorten_author_string(self.authors, 20)
        self.assertEqual(short, u"King, …, Jai…, Flash")

    def test_replace_all_but_first_name_with_ellipses(self):
        short = helper.shorten_author_string(self.authors, 10)
        self.assertEqual(short, u"King, …")

    def test_shorten_first_name_with_ellipses(self):
        short = helper.shorten_author_string(self.authors, 2)
        self.assertEqual(short, u"K…")

    def test_only_display_initial_letter_for_maxlength_1(self):
        short = helper.shorten_author_string(self.authors, 1)
        self.assertEqual(short, u"K")


class TestShellQuote(unittest.TestCase):

    def test_all_strings_are_sourrounded_by_single_quotes(self):
        quoted = helper.shell_quote("hello")
        self.assertEqual(quoted, "'hello'")

    def test_single_quotes_are_escaped_using_double_quotes(self):
        quoted = helper.shell_quote("hello'there")
        self.assertEqual(quoted, """'hello'"'"'there'""")


class TestHumanizeSize(unittest.TestCase):

    def test_small_numbers_are_converted_to_strings_directly(self):
        readable = helper.humanize_size(1)
        self.assertEqual(readable, "1")
        readable = helper.humanize_size(123)
        self.assertEqual(readable, "123")

    def test_numbers_above_1024_are_converted_to_kilobyte(self):
        readable = helper.humanize_size(1023)
        self.assertEqual(readable, "1023")
        readable = helper.humanize_size(1024)
        self.assertEqual(readable, "1K")
        readable = helper.humanize_size(1234)
        self.assertEqual(readable, "1K")

    def test_numbers_above_1048576_are_converted_to_megabyte(self):
        readable = helper.humanize_size(1024*1024-1)
        self.assertEqual(readable, "1023K")
        readable = helper.humanize_size(1024*1024)
        self.assertEqual(readable, "1.0M")

    def test_megabyte_numbers_are_converted_with_precision_1(self):
        readable = helper.humanize_size(1234*1024)
        self.assertEqual(readable, "1.2M")

    def test_numbers_are_not_converted_to_gigabyte(self):
        readable = helper.humanize_size(1234*1024*1024)
        self.assertEqual(readable, "1234.0M")
