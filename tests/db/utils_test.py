# encoding: utf-8
# Copyright (C) 2017 Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import email
import email.header
import os
import os.path
import unittest

from alot.db import utils


class TestGetParams(unittest.TestCase):

    mailstring = '\n'.join([
        'From: me',
        'To: you',
        'Subject: header field capitalisation',
        'Content-type: text/plain; charset=utf-8',
        'X-Header: param=one; and=two; or=three',
        "X-Quoted: param=utf-8''%C3%9Cmlaut; second=plain%C3%9C",
        'X-UPPERCASE: PARAM1=ONE; PARAM2=TWO'
        '\n',
        'content'
        ])
    mail = email.message_from_string(mailstring)

    def test_returns_content_type_parameters_by_default(self):
        actual = utils.get_params(self.mail)
        expected = {'text/plain': '', 'charset': 'utf-8'}
        self.assertDictEqual(actual, expected)

    def test_can_return_params_of_any_header_field(self):
        actual = utils.get_params(self.mail, header='x-header')
        expected = {'param': 'one', 'and': 'two', 'or': 'three'}
        self.assertDictEqual(actual, expected)

    @unittest.expectedFailure
    def test_parameters_are_decoded(self):
        actual = utils.get_params(self.mail, header='x-quoted')
        expected = {'param': 'Ümlaut', 'second': 'plain%C3%9C'}
        self.assertDictEqual(actual, expected)

    def test_parameters_names_are_converted_to_lowercase(self):
        actual = utils.get_params(self.mail, header='x-uppercase')
        expected = {'param1': 'ONE', 'param2': 'TWO'}
        self.assertDictEqual(actual, expected)

    def test_returns_empty_dict_if_header_not_present(self):
        actual = utils.get_params(self.mail, header='x-header-not-present')
        self.assertDictEqual(actual, dict())

    def test_returns_failobj_if_header_not_present(self):
        failobj = [('my special failobj for the test', 'needs to be a pair!')]
        actual = utils.get_params(self.mail, header='x-header-not-present',
                                  failobj=failobj)
        expected = dict(failobj)
        self.assertEqual(actual, expected)


class TestIsSubdirOf(unittest.TestCase):

    def test_both_paths_absolute_matching(self):
        superpath = '/a/b'
        subpath = '/a/b/c/d.rst'
        result = utils.is_subdir_of(subpath, superpath)
        self.assertTrue(result)

    def test_both_paths_absolute_not_matching(self):
        superpath = '/a/z'
        subpath = '/a/b/c/d.rst'
        result = utils.is_subdir_of(subpath, superpath)
        self.assertFalse(result)

    def test_both_paths_relative_matching(self):
        superpath = 'a/b'
        subpath = 'a/b/c/d.rst'
        result = utils.is_subdir_of(subpath, superpath)
        self.assertTrue(result)

    def test_both_paths_relative_not_matching(self):
        superpath = 'a/z'
        subpath = 'a/b/c/d.rst'
        result = utils.is_subdir_of(subpath, superpath)
        self.assertFalse(result)

    def test_relative_path_and_absolute_path_matching(self):
        superpath = 'a/b'
        subpath = os.path.join(os.getcwd(), 'a/b/c/d.rst')
        result = utils.is_subdir_of(subpath, superpath)
        self.assertTrue(result)


class TestExtractHeader(unittest.TestCase):

    mailstring = '\n'.join([
        'From: me',
        'To: you',
        'Subject: header field capitalisation',
        'Content-type: text/plain; charset=utf-8',
        'X-Header: param=one; and=two; or=three',
        "X-Quoted: param=utf-8''%C3%9Cmlaut; second=plain%C3%9C",
        'X-UPPERCASE: PARAM1=ONE; PARAM2=TWO'
        '\n',
        'content'
        ])
    mail = email.message_from_string(mailstring)

    def test_default_arguments_yield_all_headers(self):
        actual = utils.extract_headers(self.mail)
        # collect all lines until the first empty line, hence all header lines
        expected = []
        for line in self.mailstring.splitlines():
            if not line:
                break
            expected.append(line)
        expected = u'\n'.join(expected) + u'\n'
        self.assertEqual(actual, expected)

    def test_single_headers_can_be_retrieved(self):
        actual = utils.extract_headers(self.mail, ['from'])
        expected = u'from: me\n'
        self.assertEqual(actual, expected)

    def test_multible_headers_can_be_retrieved_in_predevined_order(self):
        headers = ['x-header', 'to', 'x-uppercase']
        actual = utils.extract_headers(self.mail, headers)
        expected = u'x-header: param=one; and=two; or=three\nto: you\n' \
            u'x-uppercase: PARAM1=ONE; PARAM2=TWO\n'
        self.assertEqual(actual, expected)

    def test_headers_can_be_retrieved_multible_times(self):
        headers = ['from', 'from']
        actual = utils.extract_headers(self.mail, headers)
        expected = u'from: me\nfrom: me\n'
        self.assertEqual(actual, expected)

    def test_case_is_prserved_in_header_keys_but_irelevant(self):
        headers = ['FROM', 'from']
        actual = utils.extract_headers(self.mail, headers)
        expected = u'FROM: me\nfrom: me\n'
        self.assertEqual(actual, expected)

    @unittest.expectedFailure
    def test_header_values_are_not_decoded(self):
        actual = utils.extract_headers(self.mail, ['x-quoted'])
        expected = u"x-quoted: param=utf-8''%C3%9Cmlaut; second=plain%C3%9C\n",
        self.assertEqual(actual, expected)


class TestEncodeHeader(unittest.TestCase):

    def test_only_value_is_used_in_output(self):
        actual = utils.encode_header('x-key', 'value')
        expected = email.header.Header('value')
        self.assertEqual(actual, expected)

    def test_unicode_chars_are_encoded(self):
        actual = utils.encode_header('x-key', u'välüe')
        expected = email.header.Header('=?utf-8?b?dsOkbMO8ZQ==?=')
        self.assertEqual(actual, expected)

    def test_space_around_email_address_is_striped(self):
        address = '  someone <user@example.com>  '
        actual = utils.encode_header('from', address)
        expected = email.header.Header(address.strip())
        self.assertEqual(actual, expected)

    def test_spaces_in_user_names_are_accepted(self):
        address = 'some one <user@example.com>'
        actual = utils.encode_header('from', address)
        expected = email.header.Header(address)
        self.assertEqual(actual, expected)

    def test_multible_addresses_can_be_given(self):
        addresses = 'one <guy@example.com>, other <guy@example.com>, ' \
            'last <guy@example.com>'
        actual = utils.encode_header('from', addresses)
        expected = email.header.Header(addresses)
        self.assertEqual(actual, expected)

    @unittest.expectedFailure
    def test_comma_in_names_are_allowed(self):
        addresses = '"last, first" <guy@example.com>, ' \
            '"name, other" <guy@example.com>'
        actual = utils.encode_header('from', addresses)
        expected = email.header.Header(addresses)
        self.assertEqual(str(actual), str(expected))
