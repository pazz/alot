# encoding: utf-8
# Copyright (C) 2017 Lucas Hoffmann
# Copyright © 2017 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import base64
import email
import email.header
import email.mime.application
import io
import os
import os.path
import shutil
import tempfile
import unittest

import gpg
import mock

from alot import crypto
from alot import helper
from alot.db import utils
from alot.errors import GPGProblem
from alot.settings.errors import NoMailcapEntry
from ..utilities import make_key, make_uid, TestCaseClassCleanup


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

    def check(self, key, valid, error_msg=u''):
        mail = self.FakeMail()

        with mock.patch('alot.db.utils.crypto.get_key',
                        mock.Mock(return_value=key)), \
                mock.patch('alot.db.utils.crypto.check_uid_validity',
                           mock.Mock(return_value=valid)):
            utils.add_signature_headers(mail, [mock.Mock(fpr='')], error_msg)

        return mail

    def test_length_0(self):
        mail = self.FakeMail()
        utils.add_signature_headers(mail, [], u'')
        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'False'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Invalid: no signature found'),
            mail.headers)

    def test_valid(self):
        key = make_key()
        mail = self.check(key, True)

        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'True'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Valid: mocked'), mail.headers)

    def test_untrusted(self):
        key = make_key()
        mail = self.check(key, False)

        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'True'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Untrusted: mocked'), mail.headers)

    def test_unicode_as_bytes(self):
        mail = self.FakeMail()
        key = make_key()
        key.uids = [make_uid('andreá@example.com',
                             uid=u'Andreá'.encode('utf-8'))]
        mail = self.check(key, True)

        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'True'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Valid: Andreá'), mail.headers)

    def test_error_message_unicode(self):
        mail = self.check(mock.Mock(), mock.Mock(), u'error message')
        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'False'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Invalid: error message'),
            mail.headers)

    def test_error_message_bytes(self):
        mail = self.check(mock.Mock(), mock.Mock(), b'error message')
        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'False'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Invalid: error message'),
            mail.headers)

    def test_get_key_fails(self):
        mail = self.FakeMail()
        with mock.patch('alot.db.utils.crypto.get_key',
                        mock.Mock(side_effect=GPGProblem(u'', 0))):
            utils.add_signature_headers(mail, [mock.Mock(fpr='')], u'')
        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'False'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Untrusted: '),
            mail.headers)


class TestMessageFromFile(TestCaseClassCleanup):

    @classmethod
    def setUpClass(cls):
        home = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, home)
        mock_home = mock.patch.dict(os.environ, {'GNUPGHOME': home})
        mock_home.start()
        cls.addClassCleanup(mock_home.stop)

        with gpg.core.Context() as ctx:
            search_dir = os.path.join(os.path.dirname(__file__),
                                      '../static/gpg-keys')
            for each in os.listdir(search_dir):
                if os.path.splitext(each)[1] == '.gpg':
                    with open(os.path.join(search_dir, each)) as f:
                        ctx.op_import(f)

            cls.keys = [ctx.get_key("DD19862809A7573A74058FF255937AFBB156245D")]

    def test_erase_alot_header_signature_valid(self):
        """Alot uses special headers for passing certain kinds of information,
        it's important that information isn't passed in from the original
        message as a way to trick the user.
        """
        m = email.message.Message()
        m.add_header(utils.X_SIGNATURE_VALID_HEADER, 'Bad')
        message = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIs(message.get(utils.X_SIGNATURE_VALID_HEADER), None)

    def test_erase_alot_header_message(self):
        m = email.message.Message()
        m.add_header(utils.X_SIGNATURE_MESSAGE_HEADER, 'Bad')
        message = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIs(message.get(utils.X_SIGNATURE_MESSAGE_HEADER), None)

    def test_plain_mail(self):
        m = email.mime.text.MIMEText(u'This is some text', 'plain', 'utf-8')
        m['Subject'] = 'test'
        m['From'] = 'me'
        m['To'] = 'Nobody'
        message = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertEqual(message.get_payload(), 'This is some text')

    def _make_signed(self):
        """Create a signed message that is multipart/signed."""
        text = 'This is some text'
        t = email.mime.text.MIMEText(text, 'plain', 'utf-8')
        _, sig = crypto.detached_signature_for(
            helper.email_as_string(t), self.keys)
        s = email.mime.application.MIMEApplication(
            sig, 'pgp-signature', email.encoders.encode_7or8bit)
        m = email.mime.multipart.MIMEMultipart('signed', None, [t, s])
        m.set_param('protocol', 'application/pgp-signature')
        m.set_param('micalg', 'pgp-sha256')
        return m

    def test_signed_headers_included(self):
        """Headers are added to the message."""
        m = self._make_signed()
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn(utils.X_SIGNATURE_VALID_HEADER, m)
        self.assertIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)

    def test_signed_valid(self):
        """Test that the signature is valid."""
        m = self._make_signed()
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertEqual(m[utils.X_SIGNATURE_VALID_HEADER], 'True')

    def test_signed_correct_from(self):
        """Test that the signature is valid."""
        m = self._make_signed()
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        # Don't test for valid/invalid since that might change
        self.assertIn('ambig <ambig@example.com>', m[utils.X_SIGNATURE_MESSAGE_HEADER])

    def test_signed_wrong_mimetype_second_payload(self):
        m = self._make_signed()
        m.get_payload(1).set_type('text/plain')
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn('expected Content-Type: ',
                      m[utils.X_SIGNATURE_MESSAGE_HEADER])

    def test_signed_wrong_micalg(self):
        m = self._make_signed()
        m.set_param('micalg', 'foo')
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn('expected micalg=pgp-...',
                      m[utils.X_SIGNATURE_MESSAGE_HEADER])

    def test_signed_micalg_cap(self):
        """The micalg parameter should be normalized to lower case.

        From RFC 3156 § 5

            The "micalg" parameter for the "application/pgp-signature" protocol
            MUST contain exactly one hash-symbol of the format "pgp-<hash-
            identifier>", where <hash-identifier> identifies the Message
            Integrity Check (MIC) algorithm used to generate the signature.
            Hash-symbols are constructed from the text names registered in [1]
            or according to the mechanism defined in that document by
            converting the text name to lower case and prefixing it with the
            four characters "pgp-".

        The spec is pretty clear that this is supposed to be lower cased.
        """
        m = self._make_signed()
        m.set_param('micalg', 'PGP-SHA1')
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn('expected micalg=pgp-',
                      m[utils.X_SIGNATURE_MESSAGE_HEADER])

    def test_signed_more_than_two_messages(self):
        """Per the spec only 2 payloads may be encapsulated inside the
        multipart/signed payload, while it might be nice to cover more than 2
        payloads (Postel's law), it would introduce serious complexity
        since we would also need to cover those payloads being misordered.
        Since getting the right number of payloads and getting them in the
        right order should be fairly easy to implement correctly enforcing that
        there are only two payloads seems reasonable.
        """
        m = self._make_signed()
        m.attach(email.mime.text.MIMEText('foo'))
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn('expected exactly two messages, got 3',
                      m[utils.X_SIGNATURE_MESSAGE_HEADER])

    # TODO: The case of more than two payloads, or the payloads being out of
    # order. Also for the encrypted case.

    def _make_encrypted(self, signed=False):
        """Create an encrypted (and optionally signed) message."""
        if signed:
            t = self._make_signed()
        else:
            text = 'This is some text'
            t = email.mime.text.MIMEText(text, 'plain', 'utf-8')
        enc = crypto.encrypt(t.as_string(), self.keys)
        e = email.mime.application.MIMEApplication(
            enc, 'octet-stream', email.encoders.encode_7or8bit)

        f = email.mime.application.MIMEApplication(
            b'Version: 1', 'pgp-encrypted', email.encoders.encode_7or8bit)

        m = email.mime.multipart.MIMEMultipart('encrypted', None, [f, e])
        m.set_param('protocol', 'application/pgp-encrypted')

        return m

    def test_encrypted_length(self):
        # It seems string that we just attach the unsigned message to the end
        # of the mail, rather than replacing the whole encrypted payload with
        # it's unencrypted equivalent
        m = self._make_encrypted()
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertEqual(len(m.get_payload()), 3)

    def test_encrypted_unsigned_is_decrypted(self):
        m = self._make_encrypted()
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        # Check using m.walk, since we're not checking for ordering, just
        # existence.
        self.assertIn('This is some text', [n.get_payload() for n in m.walk()])

    def test_encrypted_unsigned_doesnt_add_signed_headers(self):
        """Since the message isn't signed, it shouldn't have headers saying
        that there is a signature.
        """
        m = self._make_encrypted()
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertNotIn(utils.X_SIGNATURE_VALID_HEADER, m)
        self.assertNotIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)

    def test_encrypted_signed_is_decrypted(self):
        m = self._make_encrypted(True)
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn('This is some text', [n.get_payload() for n in m.walk()])

    def test_encrypted_signed_headers(self):
        """Since the message is signed, it should have headers saying that
        there is a signature.
        """
        m = self._make_encrypted(True)
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)
        self.assertIn('ambig <ambig@example.com>', m[utils.X_SIGNATURE_MESSAGE_HEADER])

    # TODO: tests for the RFC 2440 style combined signed/encrypted blob

    def test_encrypted_wrong_mimetype_first_payload(self):
        m = self._make_encrypted()
        m.get_payload(0).set_type('text/plain')
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn('Malformed OpenPGP message:',
                      m.get_payload(2).get_payload())

    def test_encrypted_wrong_mimetype_second_payload(self):
        m = self._make_encrypted()
        m.get_payload(1).set_type('text/plain')
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn('Malformed OpenPGP message:',
                      m.get_payload(2).get_payload())

    def test_signed_in_multipart_mixed(self):
        """It is valid to encapsulate a multipart/signed payload inside a
        multipart/mixed payload, verify that works.
        """
        s = self._make_signed()
        m = email.mime.multipart.MIMEMultipart('mixed', None, [s])
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn(utils.X_SIGNATURE_VALID_HEADER, m)
        self.assertIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)

    def test_encrypted_unsigned_in_multipart_mixed(self):
        """It is valid to encapsulate a multipart/encrypted payload inside a
        multipart/mixed payload, verify that works.
        """
        s = self._make_encrypted()
        m = email.mime.multipart.MIMEMultipart('mixed', None, [s])
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn('This is some text', [n.get_payload() for n in m.walk()])
        self.assertNotIn(utils.X_SIGNATURE_VALID_HEADER, m)
        self.assertNotIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)

    def test_encrypted_signed_in_multipart_mixed(self):
        """It is valid to encapsulate a multipart/encrypted payload inside a
        multipart/mixed payload, verify that works when the multipart/encrypted
        contains a multipart/signed.
        """
        s = self._make_encrypted(True)
        m = email.mime.multipart.MIMEMultipart('mixed', None, [s])
        m = utils.message_from_file(io.BytesIO(m.as_string()))
        self.assertIn('This is some text', [n.get_payload() for n in m.walk()])
        self.assertIn(utils.X_SIGNATURE_VALID_HEADER, m)
        self.assertIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)


class TestExtractBody(unittest.TestCase):

    @staticmethod
    def _set_basic_headers(mail):
        mail['Subject'] = 'Test email'
        mail['To'] = 'foo@example.com'
        mail['From'] = 'bar@example.com'

    def test_single_text_plain(self):
        mail = email.mime.text.MIMEText('This is an email')
        self._set_basic_headers(mail)
        actual = utils.extract_body(mail)

        expected = 'This is an email'

        self.assertEqual(actual, expected)

    def test_two_text_plain(self):
        mail = email.mime.multipart.MIMEMultipart()
        self._set_basic_headers(mail)
        mail.attach(email.mime.text.MIMEText('This is an email'))
        mail.attach(email.mime.text.MIMEText('This is a second part'))

        actual = utils.extract_body(mail)
        expected = 'This is an email\n\nThis is a second part'

        self.assertEqual(actual, expected)

    def test_unknown_part(self):
        mail = email.mime.multipart.MIMEMultipart()
        self._set_basic_headers(mail)
        # add an "application/octet-stream" part without marking it with
        # content-Disposition attachment.
        mail.attach(email.mime.application.MIMEApplication(b'1'))

        # this will fail to find a mailcap entry for rendeting octet-stream.
        self.assertRaises(NoMailcapEntry, utils.extract_body, mail)

    def test_text_plain_with_attachment_text(self):
        mail = email.mime.multipart.MIMEMultipart()
        self._set_basic_headers(mail)
        mail.attach(email.mime.text.MIMEText('This is an email'))
        attachment = email.mime.text.MIMEText('this shouldnt be displayed')
        attachment['Content-Disposition'] = 'attachment'
        mail.attach(attachment)

        actual = utils.extract_body(mail)
        expected = 'This is an email'

        self.assertEqual(actual, expected)

    def _make_mixed_plain_html(self):
        mail = email.mime.multipart.MIMEMultipart()
        self._set_basic_headers(mail)
        mail.attach(email.mime.text.MIMEText('This is an email'))
        mail.attach(email.mime.text.MIMEText(
            '<!DOCTYPE html><html><body>This is an html email</body></html>',
            'html'))
        return mail

    @mock.patch('alot.db.utils.settings.get', mock.Mock(return_value=True))
    def test_prefer_plaintext(self):
        expected = 'This is an email'
        mail = self._make_mixed_plain_html()
        actual = utils.extract_body(mail)

        self.assertEqual(actual, expected)

    # Mock the handler to cat, so that no transformations of the html are made
    # making the result non-deterministic
    @mock.patch('alot.db.utils.settings.get', mock.Mock(return_value=False))
    @mock.patch('alot.db.utils.settings.mailcap_find_match',
                mock.Mock(return_value=(None, {'view': 'cat'})))
    def test_prefer_html(self):
        expected = '<!DOCTYPE html><html><body>This is an html email</body></html>'
        mail = self._make_mixed_plain_html()
        actual = utils.extract_body(mail)

        self.assertEqual(actual, expected)

    @mock.patch('alot.db.utils.settings.get', mock.Mock(return_value=False))
    @mock.patch('alot.db.utils.settings.mailcap_find_match',
                mock.Mock(return_value=(None, {'view': 'cat'})))
    def test_types_provided(self):
        # This should not return html, even though html is set to preferred
        # since a types variable is passed
        expected = 'This is an email'
        mail = self._make_mixed_plain_html()
        actual = utils.extract_body(mail, types=['text/plain'])

        self.assertEqual(actual, expected)

    @mock.patch('alot.db.utils.settings.mailcap_find_match',
                mock.Mock(return_value=(None, {'view': 'cat'})))
    def test_require_mailcap_stdin(self):
        mail = email.mime.multipart.MIMEMultipart()
        self._set_basic_headers(mail)
        mail.attach(email.mime.text.MIMEText(
            '<!DOCTYPE html><html><body>This is an html email</body></html>',
            'html'))
        actual = utils.extract_body(mail)
        expected = '<!DOCTYPE html><html><body>This is an html email</body></html>'

        self.assertEqual(actual, expected)

    @mock.patch('alot.db.utils.settings.mailcap_find_match',
                mock.Mock(return_value=(None, {'view': 'cat %s'})))
    def test_require_mailcap_file(self):
        mail = email.mime.multipart.MIMEMultipart()
        self._set_basic_headers(mail)
        mail.attach(email.mime.text.MIMEText(
            '<!DOCTYPE html><html><body>This is an html email</body></html>',
            'html'))
        actual = utils.extract_body(mail)
        expected = '<!DOCTYPE html><html><body>This is an html email</body></html>'

        self.assertEqual(actual, expected)


class TestMessageFromString(unittest.TestCase):

    """Tests for message_from_string.

    Because the implementation is that this is a wrapper around
    message_from_file, it's not important to have a large swath of tests, just
    enough to show that things are being passed correctly.
    """

    def test(self):
        m = email.mime.text.MIMEText(u'This is some text', 'plain', 'utf-8')
        m['Subject'] = 'test'
        m['From'] = 'me'
        m['To'] = 'Nobody'
        message = utils.message_from_string(m.as_string())
        self.assertEqual(message.get_payload(), 'This is some text')
