# encoding: utf-8
# Copyright (C) 2017 Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import base64
import email
import email.header
import os
import os.path
import unittest

import mock

from alot.db import utils
from ..crypto_test import make_key


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

    def test_plain_email_addresses_are_accepted(self):
        address = 'user@example.com'
        actual = utils.encode_header('from', address)
        expected = email.header.Header(address)
        self.assertEqual(actual, expected)

    def test_email_addresses_with_realnames_are_accepted(self):
        address = 'someone <user@example.com>'
        actual = utils.encode_header('from', address)
        expected = email.header.Header(address)
        self.assertEqual(actual, expected)

    def test_email_addresses_with_empty_realnames_are_treated_like_plain(self):
        address = 'user@example.com'
        empty_realname = '<'+address+'>'
        actual = utils.encode_header('from', empty_realname)
        expected = email.header.Header(address)
        self.assertEqual(str(actual), str(expected))

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

    def test_comma_in_names_are_allowed(self):
        addresses = '"last, first" <guy@example.com>, ' \
            '"name, other" <guy@example.com>'
        actual = utils.encode_header('from', addresses)
        expected = email.header.Header(addresses)
        self.assertEqual(str(actual), str(expected))

    def test_utf_8_chars_in_realnames_are_accepted(self):
        address = u'Ümlaut <uemlaut@example.com>'
        actual = utils.encode_header('from', address)
        expected = email.header.Header(
            '=?utf-8?q?=C3=9Cmlaut?= <uemlaut@example.com>')
        self.assertEqual(actual, expected)


class TestDecodeHeader(unittest.TestCase):

    @staticmethod
    def _quote(unicode_string, encoding):
        """Turn a unicode string into a RFC2047 quoted ascii string

        :param unicode_string: the string to encode
        :type unicode_string: unicode
        :param encoding: the encoding to use, 'utf-8', 'iso-8859-1', ...
        :type encoding: str
        :returns: the encoded string
        :rtype: str
        """
        string = unicode_string.encode(encoding)
        output = '=?' + encoding + '?Q?'
        for byte in string:
            output += '=' + byte.encode('hex').upper()
        return output + '?='

    @staticmethod
    def _base64(unicode_string, encoding):
        """Turn a unicode string into a RFC2047 base64 encoded ascii string

        :param unicode_string: the string to encode
        :type unicode_string: unicode
        :param encoding: the encoding to use, 'utf-8', 'iso-8859-1', ...
        :type encoding: str
        :returns: the encoded string
        :rtype: str
        """
        string = unicode_string.encode(encoding)
        b64 = base64.encodestring(string).strip()
        return '=?' + encoding + '?B?' + b64 + '?='


    def _test(self, teststring, expected):
        actual = utils.decode_header(teststring)
        self.assertEqual(actual, expected)

    def test_non_ascii_strings_are_returned_as_unicode_directly(self):
        text = u'Nön ÄSCII string¡'
        self._test(text, text)

    def test_basic_utf_8_quoted(self):
        expected = u'ÄÖÜäöü'
        text = self._quote(expected, 'utf-8')
        self._test(text, expected)

    def test_basic_iso_8859_1_quoted(self):
        expected = u'ÄÖÜäöü'
        text = self._quote(expected, 'iso-8859-1')
        self._test(text, expected)

    def test_basic_windows_1252_quoted(self):
        expected = u'ÄÖÜäöü'
        text = self._quote(expected, 'windows-1252')
        self._test(text, expected)

    def test_basic_utf_8_base64(self):
        expected = u'ÄÖÜäöü'
        text = self._base64(expected, 'utf-8')
        self._test(text, expected)

    def test_basic_iso_8859_1_base64(self):
        expected = u'ÄÖÜäöü'
        text = self._base64(expected, 'iso-8859-1')
        self._test(text, expected)

    def test_basic_iso_1252_base64(self):
        expected = u'ÄÖÜäöü'
        text = self._base64(expected, 'windows-1252')
        self._test(text, expected)

    def test_quoted_words_can_be_interrupted(self):
        part = u'ÄÖÜäöü'
        text = self._base64(part, 'utf-8') + ' and ' + \
            self._quote(part, 'utf-8')
        expected = u'ÄÖÜäöü and ÄÖÜäöü'
        self._test(text, expected)

    def test_different_encodings_can_be_mixed(self):
        part = u'ÄÖÜäöü'
        text = 'utf-8: ' + self._base64(part, 'utf-8') + \
            ' again: ' + self._quote(part, 'utf-8') + \
            ' latin1: ' + self._base64(part, 'iso-8859-1') + \
            ' and ' + self._quote(part, 'iso-8859-1')
        expected = u'utf-8: ÄÖÜäöü again: ÄÖÜäöü latin1: ÄÖÜäöü and ÄÖÜäöü'
        self._test(text, expected)

    def test_tabs_are_expanded_to_align_with_eigth_spaces(self):
        text = 'tab: \t'
        expected = u'tab:    '
        self._test(text, expected)

    def test_newlines_are_not_touched_by_default(self):
        text = 'first\nsecond\n third\n  fourth'
        expected = u'first\nsecond\n third\n  fourth'
        self._test(text, expected)

    def test_continuation_newlines_can_be_normalized(self):
        text = 'first\nsecond\n third\n\tfourth\n \t  fifth'
        expected = u'first\nsecond third fourth fifth'
        actual = utils.decode_header(text, normalize=True)
        self.assertEqual(actual, expected)


class TestAddSignatureHeaders(unittest.TestCase):

    class FakeMail(object):
        def __init__(self):
            self.headers = []

        def add_header(self, header, value):
            self.headers.append((header, value))

    def test_length_0(self):
        mail = self.FakeMail()
        utils.add_signature_headers(mail, [], u'')
        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'False'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Invalid: no signature found'),
            mail.headers)

    def test_valid(self):
        mail = self.FakeMail()
        key = make_key()

        with mock.patch('alot.db.utils.crypto.get_key',
                        mock.Mock(return_value=key)), \
                mock.patch('alot.db.utils.crypto.check_uid_validity',
                           mock.Mock(return_value=True)):
            utils.add_signature_headers(mail, [mock.Mock(fpr=None)], u'')

        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'True'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Valid: mocked'), mail.headers)

    def test_untrusted(self):
        mail = self.FakeMail()
        key = make_key()

        with mock.patch('alot.db.utils.crypto.get_key',
                        mock.Mock(return_value=key)), \
                mock.patch('alot.db.utils.crypto.check_uid_validity',
                           mock.Mock(return_value=False)):
            utils.add_signature_headers(mail, [mock.Mock(fpr=None)], u'')

        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'True'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Untrusted: mocked'), mail.headers)
