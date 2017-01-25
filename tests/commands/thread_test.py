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


class TestClearMyAddress(unittest.TestCase):

    me1 = 'me@example.com'
    me2 = 'ME@example.com'
    me_named = 'alot team <me@example.com>'
    you = 'you@example.com'
    named = 'somebody you know <somebody@example.com>'
    imposter = 'alot team <imposter@example.com>'
    mine = [me1, me2]

    def test_empty_input_returns_empty_list(self):
        self.assertListEqual(
            thread.ReplyCommand.clear_my_address(self.mine, []), [])

    def test_only_my_emails_result_in_empty_list(self):
        expected = []
        actual = thread.ReplyCommand.clear_my_address(self.mine,
                                                      self.mine+[self.me_named])
        self.assertListEqual(actual, expected)

    def test_other_emails_are_untouched(self):
        input_ = [self.you, self.me1, self.me_named, self.named]
        expected = [self.you, self.named]
        actual = thread.ReplyCommand.clear_my_address(self.mine, input_)
        self.assertListEqual(actual, expected)

    def test_case_matters(self):
        expected = [self.me1]
        mine = [self.me2]
        actual = thread.ReplyCommand.clear_my_address(mine, expected)
        self.assertListEqual(actual, expected)

    def test_same_address_with_different_real_name_is_removed(self):
        input_ = [self.me_named, self.you]
        mine = [self.me1]
        expected = [self.you]
        actual = thread.ReplyCommand.clear_my_address(mine, input_)
        self.assertListEqual(actual, expected)

    def test_real_name_is_never_considered(self):
        expected = [self.imposter]
        mine = 'alot team'
        actual = thread.ReplyCommand.clear_my_address(mine, expected)
        self.assertListEqual(actual, expected)
