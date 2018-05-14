# encoding=utf-8
# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Test suite for alot.commands.thread module."""
from __future__ import absolute_import

import email

import mock
from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks, returnValue

from alot.commands import thread
from alot.account import Account

# Good descriptive test names often don't fit PEP8, which is meant to cover
# functions meant to be called by humans.
# pylint: disable=invalid-name

# These are tests, don't worry about names like "foo" and "bar"
# pylint: disable=blacklisted-name


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
        actual = thread.ReplyCommand.clear_my_address(
            self.mine, self.mine+[self.me_named])
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


class _AccountTestClass(Account):
    """Implements stubs for ABC methods."""

    def send_mail(self, mail):
        pass


class TestDetermineSender(unittest.TestCase):

    header_priority = ["From", "To", "Cc", "Envelope-To", "X-Envelope-To",
                       "Delivered-To"]
    mailstring = '\n'.join([
        "From: from@example.com",
        "To: to@example.com",
        "Cc: cc@example.com",
        "Envelope-To: envelope-to@example.com",
        "X-Envelope-To: x-envelope-to@example.com",
        "Delivered-To: delivered-to@example.com",
        "Subject: Alot test",
        "\n",
        "Some content",
        ])
    mail = email.message_from_string(mailstring)

    @inlineCallbacks
    def _test(self, accounts=(), expected=(), mail=None, header_priority=None,
              force_realname=False, force_address=False):
        """This method collects most of the steps that need to be done for most
        tests.  Especially a closure to mock settings.get and a mock for
        settings.get_accounts are set up."""
        mail = self.mail if mail is None else mail
        header_priority = self.header_priority if header_priority is None \
            else header_priority

        def settings_get(arg):
            """Mock function for setting.get()"""
            if arg == "reply_account_header_priority":
                return header_priority
            elif arg.endswith('_force_realname'):
                return force_realname
            elif arg.endswith('_force_address'):
                return force_address

        with mock.patch('alot.commands.thread.settings.get_accounts',
                        mock.Mock(return_value=accounts)):
            with mock.patch('alot.commands.thread.settings.get', settings_get):
                actual = yield thread.determine_sender(mail, mock.Mock())
        self.assertTupleEqual(actual, expected)

    @inlineCallbacks
    def test_assert_that_some_accounts_are_defined(self):
        with mock.patch('alot.commands.thread.settings.get_accounts',
                        mock.Mock(return_value=[])) as cm1:
            with self.assertRaises(AssertionError) as cm2:
                yield thread.determine_sender(None, mock.Mock())
        expected = ('no accounts set!',)
        cm1.assert_called_once_with()
        self.assertTupleEqual(cm2.exception.args, expected)

    @inlineCallbacks
    def test_default_account_is_used_if_no_match_is_found(self):
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'bar@example.com')
        expected = (u'foo@example.com', account1)
        yield self._test(accounts=[account1, account2], expected=expected)

    @inlineCallbacks
    def test_matching_address_and_account_are_returned(self):
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'to@example.com')
        account3 = _AccountTestClass(address=u'bar@example.com')
        expected = (u'to@example.com', account2)
        yield self._test(accounts=[account1, account2, account3], expected=expected)

    @inlineCallbacks
    def test_force_realname_includes_real_name_in_returned_address_if_defined(self):
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'to@example.com', realname='Bar')
        account3 = _AccountTestClass(address=u'baz@example.com')
        expected = (u'Bar <to@example.com>', account2)
        yield self._test(accounts=[account1, account2, account3], expected=expected,
                   force_realname=True)

    @inlineCallbacks
    def test_doesnt_fail_with_force_realname_if_real_name_not_defined(self):
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'to@example.com')
        account3 = _AccountTestClass(address=u'bar@example.com')
        expected = (u'to@example.com', account2)
        yield self._test(accounts=[account1, account2, account3], expected=expected,
                   force_realname=True)

    @inlineCallbacks
    def test_with_force_address_main_address_is_used_regardless_of_matching_address(self):
        # In python 3.4 this and the next test could be written as subtests.
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'bar@example.com',
                                     aliases=[u'to@example.com'])
        account3 = _AccountTestClass(address=u'bar@example.com')
        expected = (u'bar@example.com', account2)
        yield self._test(accounts=[account1, account2, account3], expected=expected,
                   force_address=True)

    @inlineCallbacks
    def test_without_force_address_matching_address_is_used(self):
        # In python 3.4 this and the previous test could be written as
        # subtests.
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'bar@example.com',
                                     aliases=[u'to@example.com'])
        account3 = _AccountTestClass(address=u'baz@example.com')
        expected = (u'to@example.com', account2)
        yield self._test(accounts=[account1, account2, account3], expected=expected,
                   force_address=False)

    @inlineCallbacks
    def test_uses_to_header_if_present(self):
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'to@example.com')
        account3 = _AccountTestClass(address=u'bar@example.com')
        expected = (u'to@example.com', account2)
        yield self._test(accounts=[account1, account2, account3], expected=expected)

    @inlineCallbacks
    def test_header_order_is_more_important_than_accounts_order(self):
        account1 = _AccountTestClass(address=u'cc@example.com')
        account2 = _AccountTestClass(address=u'to@example.com')
        account3 = _AccountTestClass(address=u'bcc@example.com')
        expected = (u'to@example.com', account2)
        yield self._test(accounts=[account1, account2, account3], expected=expected)

    @inlineCallbacks
    def test_accounts_can_be_found_by_alias_regex_setting(self):
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'to@example.com',
                                     alias_regexp=r'to\+.*@example.com')
        account3 = _AccountTestClass(address=u'bar@example.com')
        mailstring = self.mailstring.replace(u'to@example.com',
                                             u'to+some_tag@example.com')
        mail = email.message_from_string(mailstring)
        expected = (u'to+some_tag@example.com', account2)
        yield self._test(accounts=[account1, account2, account3], expected=expected,
                   mail=mail)

    @inlineCallbacks
    def test_get_account_hook_undefined(self):
        """Test that if the hook is undefined an address is found."""
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'bar@example.com')
        expected = (u'foo@example.com', account1)

        with mock.patch('alot.commands.thread.settings.get_hook',
                        mock.Mock(return_value=None)):
            yield self._test(accounts=[account1, account2], expected=expected)

    @inlineCallbacks
    def test_get_account_hook_returns_none(self):
        """Test that if the hook returns None an address is found."""
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'bar@example.com')
        expected = (u'foo@example.com', account1)

        with mock.patch('alot.commands.thread.settings.get_hook',
                        mock.Mock(return_value=mock.Mock(return_value=None))):
            yield self._test(accounts=[account1, account2], expected=expected)

    @inlineCallbacks
    def test_get_account_hook_is_used(self):
        """Test that if the hook returns an address that is used."""
        account1 = _AccountTestClass(address=u'foo@example.com')
        account2 = _AccountTestClass(address=u'bar@example.com')
        expected = (u'bar@example.com', account2)

        @inlineCallbacks
        def hook(*_):
            yield
            returnValue(account2)

        with mock.patch('alot.commands.thread.settings.get_hook',
                        mock.Mock(return_value=hook)):
            yield self._test(accounts=[account1, account2], expected=expected)
