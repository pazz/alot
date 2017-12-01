# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import unittest

from alot import addressbook


class _AddressBook(addressbook.AddressBook):

    """Implements stubs for ABC methods.  The return value for get_contacts can
    be set on instance creation."""

    def __init__(self, contacts, **kwargs):
        self._contacts = contacts
        super(_AddressBook, self).__init__(**kwargs)

    def get_contacts(self):
        return self._contacts


class TestAddressBook(unittest.TestCase):

    def test_lookup_will_match_names(self):
        contacts = [('foo', 'x@example.com'), ('bar', 'y@example.com'),
                    ('baz', 'z@example.com')]
        abook = _AddressBook(contacts)
        actual = abook.lookup('bar')
        expected = [contacts[1]]
        self.assertListEqual(actual, expected)

    def test_lookup_will_match_emails(self):
        contacts = [('foo', 'x@example.com'), ('bar', 'y@example.com'),
                    ('baz', 'z@example.com')]
        abook = _AddressBook(contacts)
        actual = abook.lookup('y@example.com')
        expected = [contacts[1]]
        self.assertListEqual(actual, expected)

    def test_lookup_ignores_case_by_default(self):
        contacts = [('name', 'email@example.com'),
                    ('Name', 'other@example.com'),
                    ('someone', 'someone@example.com')]
        abook = _AddressBook(contacts)
        actual = abook.lookup('name')
        expected = [contacts[0], contacts[1]]
        self.assertListEqual(actual, expected)

    def test_lookup_can_match_case(self):
        contacts = [('name', 'email@example.com'),
                    ('Name', 'other@example.com'),
                    ('someone', 'someone@example.com')]
        abook = _AddressBook(contacts, ignorecase=False)
        actual = abook.lookup('name')
        expected = [contacts[0]]
        self.assertListEqual(actual, expected)

    def test_lookup_will_match_partial_in_the_middle(self):
        contacts = [('name', 'email@example.com'),
                    ('My Own Name', 'other@example.com'),
                    ('someone', 'someone@example.com')]
        abook = _AddressBook(contacts)
        actual = abook.lookup('Own')
        expected = [contacts[1]]
        self.assertListEqual(actual, expected)

    def test_lookup_can_handle_special_regex_chars(self):
        contacts = [('name [work]', 'email@example.com'),
                    ('My Own Name', 'other@example.com'),
                    ('someone', 'someone@example.com')]
        abook = _AddressBook(contacts)
        actual = abook.lookup('[wor')
        expected = [contacts[0]]
        self.assertListEqual(actual, expected)
