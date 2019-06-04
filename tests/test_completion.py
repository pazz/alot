# encoding=utf-8
# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Tests for the alot.completion module."""
import unittest

import mock

from alot import completion

# Good descriptive test names often don't fit PEP8, which is meant to cover
# functions meant to be called by humans.
# pylint: disable=invalid-name


def _mock_lookup(query):
    """Look up the query from fixed list of names and email addresses."""
    abook = [
        ("", "no-real-name@example.com"),
        ("foo", "foo@example.com"),
        ("Ümläut", "umlaut@example.com"),
        ("comma, person", "comma@example.com"),
        ("single 'quote' person", "squote@example.com"),
        ('double "quote" person', "dquote@example.com"),
        ("""all 'fanzy' "stuff" at, once""", "all@example.com")
    ]
    results = []
    for name, email in abook:
        if query in name or query in email:
            results.append((name, email))
    return results


class AbooksCompleterTest(unittest.TestCase):
    """Tests for the address book completion class."""

    @classmethod
    def setUpClass(cls):
        abook = mock.Mock()
        abook.lookup = _mock_lookup
        cls.empty_abook_completer = completion.AbooksCompleter([])
        cls.example_abook_completer = completion.AbooksCompleter([abook])

    def test_empty_address_book_returns_empty_list(self):
        actual = self.__class__.empty_abook_completer.complete('real-name', 9)
        expected = []
        self.assertListEqual(actual, expected)

    def _assert_only_one_list_entry(self, actual, expected):
        """Check that the given lists are both of length 1 and the tuple at the
        first positions are equal."""
        self.assertEqual(len(actual), 1)
        self.assertEqual(len(expected), 1)
        self.assertTupleEqual(actual[0], expected[0])

    def test_empty_real_name_returns_plain_email_address(self):
        actual = self.__class__.example_abook_completer.complete(
            "real-name", 9)
        expected = [("no-real-name@example.com", 24)]
        self._assert_only_one_list_entry(actual, expected)

    def test_simple_address_with_real_name(self):
        actual = self.__class__.example_abook_completer.complete("foo", 3)
        expected = [("foo <foo@example.com>", 21)]
        self.assertListEqual(actual, expected)

    def test_simple_address_with_umlaut_real_name(self):
        actual = self.__class__.example_abook_completer.complete("umlaut", 6)
        expected = [("Ümläut <umlaut@example.com>", 27)]
        self.assertListEqual(actual, expected)

    def test_real_name_with_comma(self):
        actual = self.__class__.example_abook_completer.complete("comma", 5)
        expected = [('"comma, person" <comma@example.com>', 35)]
        self.assertListEqual(actual, expected)

    def test_real_name_with_single_quotes(self):
        actual = self.__class__.example_abook_completer.complete("squote", 6)
        expected = [("single 'quote' person <squote@example.com>", 42)]
        self._assert_only_one_list_entry(actual, expected)

    def test_real_name_double_quotes(self):
        actual = self.__class__.example_abook_completer.complete("dquote", 6)
        expected = [("", 0)]
        expected = [
            (r"""double "quote" person <dquote@example.com>""", 42)]
        self._assert_only_one_list_entry(actual, expected)

    def test_real_name_with_quotes_and_comma(self):
        actual = self.__class__.example_abook_completer.complete("all", 3)
        expected = [(r""""all 'fanzy' "stuff" at, once" <all@example.com>""",
                     48)]
        self._assert_only_one_list_entry(actual, expected)


class StringlistCompleterTest(unittest.TestCase):
    def test_dont_choke_on_special_regex_characters(self):
        tags = ['[match]', 'nomatch']
        completer = completion.StringlistCompleter(tags)
        actual = completer.complete('[', 1)
        expected = [(tags[0], len(tags[0]))]
        self.assertListEqual(actual, expected)
