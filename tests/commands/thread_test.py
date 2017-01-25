# encoding=utf-8
# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Test suite for alot.commands.thread module."""
from __future__ import absolute_import

import unittest

from alot.commands import thread


class Test_ensure_unique_address(unittest.TestCase):

    foo = 'foo <foo@example.com>'
    foo2 = 'foo the fanzy <foo@example.com>'
    bar = 'bar <bar@example.com>'
    baz = 'baz <baz@example.com>'

    def test_unique_lists_are_unchanged(self):
        expected = sorted([self.foo, self.bar])
        actual = thread.ReplyCommand.ensure_unique_address(expected)
        self.assertListEqual(actual, expected)

    def test_equal_entries_are_detected(self):
        actual = thread.ReplyCommand.ensure_unique_address(
            [self.foo, self.bar, self.foo])
        expected = sorted([self.foo, self.bar])
        self.assertListEqual(actual, expected)

    def test_same_address_with_different_name_is_detected(self):
        actual = thread.ReplyCommand.ensure_unique_address(
            [self.foo, self.foo2])
        expected = [self.foo2]
        self.assertListEqual(actual, expected)
