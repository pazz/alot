# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import unittest
from unittest import mock

from alot.addressbook import external


class TestExternalAddressbookGetContacts(unittest.TestCase):

    """Some test cases for
    alot.addressbook.external.ExternalAddressbook.get_contacts"""

    regex = '(?P<name>.*)\t(?P<email>.*)'

    @staticmethod
    def _patch_call_cmd(return_value):
        return mock.patch('alot.addressbook.external.call_cmd',
                          mock.Mock(return_value=return_value))

    def test_raises_if_external_command_exits_with_non_zero_status(self):
        abook = external.ExternalAddressbook('foobar', '')
        with self._patch_call_cmd(('', '', 42)):
            with self.assertRaises(external.AddressbookError) as contextmgr:
                abook.get_contacts()
        expected = u'abook command "foobar" returned with return code 42'
        self.assertEqual(contextmgr.exception.args[0], expected)

    def test_stderr_of_failing_command_is_part_of_exception_message(self):
        stderr = 'some text printed on stderr of external command'
        abook = external.ExternalAddressbook('foobar', '')
        with self._patch_call_cmd(('', stderr, 42)):
            with self.assertRaises(external.AddressbookError) as contextmgr:
                abook.get_contacts()
        self.assertIn(stderr, contextmgr.exception.args[0])

    def test_returns_empty_list_when_command_returns_no_output(self):
        abook = external.ExternalAddressbook('foobar', self.regex)
        with self._patch_call_cmd(('', '', 0)) as call_cmd:
            actual = abook.get_contacts()
        self.assertListEqual(actual, [])
        call_cmd.assert_called_once_with(['foobar'])

    def test_splits_results_from_provider_by_regex(self):
        abook = external.ExternalAddressbook('foobar', self.regex)
        with self._patch_call_cmd(
                ('me\t<me@example.com>\nyou\t<you@other.domain>', '', 0)):
            actual = abook.get_contacts()
        expected = [('me', '<me@example.com>'), ('you', '<you@other.domain>')]
        self.assertListEqual(actual, expected)

    def test_returns_empty_list_if_regex_has_no_name_submatches(self):
        abook = external.ExternalAddressbook(
            'foobar', self.regex.replace('name', 'xname'))
        with self._patch_call_cmd(
                ('me\t<me@example.com>\nyou\t<you@other.domain>', '', 0)):
            actual = abook.get_contacts()
        self.assertListEqual(actual, [])

    def test_returns_empty_list_if_regex_has_no_email_submatches(self):
        abook = external.ExternalAddressbook(
            'foobar', self.regex.replace('email', 'xemail'))
        with self._patch_call_cmd(
                ('me\t<me@example.com>\nyou\t<you@other.domain>', '', 0)):
            actual = abook.get_contacts()
        self.assertListEqual(actual, [])
