# encoding: utf-8
# Copyright (C) 2017 Lucas Hoffmann
# Copyright © 2017 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import base64
import codecs
import email
import email.header
import email.mime.application
import email.policy
import email.utils
from email.message import EmailMessage
import io
import os
import os.path
import shutil
import tempfile
import unittest
from unittest import mock

import gpg

from alot import crypto
from alot.db import utils
from alot.errors import GPGProblem
from alot.account import Account
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
        output = b'=?' + encoding.encode('ascii') + b'?Q?'
        for byte in string:
            output += b'=' + codecs.encode(bytes([byte]), 'hex').upper()
        return (output + b'?=').decode('ascii')

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
        b64 = base64.encodebytes(string).strip()
        result_bytes = b'=?' + encoding.encode('utf-8') + b'?B?' + b64 + b'?='
        result = result_bytes.decode('ascii')
        return result

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
        expected = (
            u'utf-8: ÄÖÜäöü '
            u'again: ÄÖÜäöü '
            u'latin1: ÄÖÜäöü and ÄÖÜäöü'
        )
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

    def test_exchange_quotes_remain(self):
        # issue #1347
        expected = u'"Mouse, Michaël" <x@y.z>'
        text = self._quote(expected, 'utf-8')
        self._test(text, expected)


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
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Untrusted: mocked'),
            mail.headers)

    def test_unicode_as_bytes(self):
        mail = self.FakeMail()
        key = make_key()
        key.uids = [make_uid('andreá@example.com', uid=u'Andreá')]
        mail = self.check(key, True)

        self.assertIn((utils.X_SIGNATURE_VALID_HEADER, u'True'), mail.headers)
        self.assertIn(
            (utils.X_SIGNATURE_MESSAGE_HEADER, u'Valid: Andreá'),
            mail.headers)

    def test_error_message_unicode(self):
        mail = self.check(mock.Mock(), mock.Mock(), u'error message')
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

            cls.keys = [
                ctx.get_key("DD19862809A7573A74058FF255937AFBB156245D")]

    def test_erase_alot_header_signature_valid(self):
        """Alot uses special headers for passing certain kinds of information,
        it's important that information isn't passed in from the original
        message as a way to trick the user.
        """
        m = email.message.Message()
        m.add_header(utils.X_SIGNATURE_VALID_HEADER, 'Bad')
        message = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIs(message.get(utils.X_SIGNATURE_VALID_HEADER), None)

    def test_erase_alot_header_message(self):
        m = email.message.Message()
        m.add_header(utils.X_SIGNATURE_MESSAGE_HEADER, 'Bad')
        message = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIs(message.get(utils.X_SIGNATURE_MESSAGE_HEADER), None)

    def test_plain_mail(self):
        m = email.mime.text.MIMEText(u'This is some text', 'plain', 'utf-8')
        m['Subject'] = 'test'
        m['From'] = 'me'
        m['To'] = 'Nobody'
        message = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertEqual(message.get_payload(), 'This is some text')

    def _make_signed(self):
        """Create a signed message that is multipart/signed."""
        text = b'This is some text'
        t = email.mime.text.MIMEText(text, 'plain', 'utf-8')
        _, sig = crypto.detached_signature_for(
            t.as_bytes(policy=email.policy.SMTP), self.keys)
        s = email.mime.application.MIMEApplication(
            sig, 'pgp-signature', email.encoders.encode_7or8bit)
        m = email.mime.multipart.MIMEMultipart('signed', None, [t, s])
        m.set_param('protocol', 'application/pgp-signature')
        m.set_param('micalg', 'pgp-sha256')
        return m

    def test_signed_headers_included(self):
        """Headers are added to the message."""
        m = self._make_signed()
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIn(utils.X_SIGNATURE_VALID_HEADER, m)
        self.assertIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)

    def test_signed_valid(self):
        """Test that the signature is valid."""
        m = self._make_signed()
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertEqual(m[utils.X_SIGNATURE_VALID_HEADER], 'True')

    def test_signed_correct_from(self):
        """Test that the signature is valid."""
        m = self._make_signed()
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        # Don't test for valid/invalid since that might change
        self.assertIn(
            'ambig <ambig@example.com>', m[utils.X_SIGNATURE_MESSAGE_HEADER])

    def test_signed_wrong_mimetype_second_payload(self):
        m = self._make_signed()
        m.get_payload(1).set_type('text/plain')
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIn('expected Content-Type: ',
                      m[utils.X_SIGNATURE_MESSAGE_HEADER])

    def test_signed_wrong_micalg(self):
        m = self._make_signed()
        m.set_param('micalg', 'foo')
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
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
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
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
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIn('expected exactly two messages, got 3',
                      m[utils.X_SIGNATURE_MESSAGE_HEADER])

    # TODO: The case of more than two payloads, or the payloads being out of
    # order. Also for the encrypted case.

    def _make_encrypted(self, signed=False):
        """Create an encrypted (and optionally signed) message."""
        if signed:
            t = self._make_signed()
        else:
            text = b'This is some text'
            t = email.mime.text.MIMEText(text, 'plain', 'utf-8')
        enc = crypto.encrypt(t.as_bytes(policy=email.policy.SMTP), self.keys)
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
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertEqual(len(m.get_payload()), 3)

    def test_encrypted_unsigned_is_decrypted(self):
        m = self._make_encrypted()
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        # Check using m.walk, since we're not checking for ordering, just
        # existence.
        self.assertIn('This is some text', [n.get_payload() for n in m.walk()])

    def test_encrypted_unsigned_doesnt_add_signed_headers(self):
        """Since the message isn't signed, it shouldn't have headers saying
        that there is a signature.
        """
        m = self._make_encrypted()
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertNotIn(utils.X_SIGNATURE_VALID_HEADER, m)
        self.assertNotIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)

    def test_encrypted_signed_is_decrypted(self):
        m = self._make_encrypted(True)
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIn('This is some text', [n.get_payload() for n in m.walk()])

    def test_encrypted_signed_headers(self):
        """Since the message is signed, it should have headers saying that
        there is a signature.
        """
        m = self._make_encrypted(True)
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)
        self.assertIn(
            'ambig <ambig@example.com>', m[utils.X_SIGNATURE_MESSAGE_HEADER])

    # TODO: tests for the RFC 2440 style combined signed/encrypted blob

    def test_encrypted_wrong_mimetype_first_payload(self):
        m = self._make_encrypted()
        m.get_payload(0).set_type('text/plain')
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIn('Malformed OpenPGP message:',
                      m.get_payload(2).get_payload())

    def test_encrypted_wrong_mimetype_second_payload(self):
        m = self._make_encrypted()
        m.get_payload(1).set_type('text/plain')
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIn('Malformed OpenPGP message:',
                      m.get_payload(2).get_payload())

    def test_signed_in_multipart_mixed(self):
        """It is valid to encapsulate a multipart/signed payload inside a
        multipart/mixed payload, verify that works.
        """
        s = self._make_signed()
        m = email.mime.multipart.MIMEMultipart('mixed', None, [s])
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
        self.assertIn(utils.X_SIGNATURE_VALID_HEADER, m)
        self.assertIn(utils.X_SIGNATURE_MESSAGE_HEADER, m)

    def test_encrypted_unsigned_in_multipart_mixed(self):
        """It is valid to encapsulate a multipart/encrypted payload inside a
        multipart/mixed payload, verify that works.
        """
        s = self._make_encrypted()
        m = email.mime.multipart.MIMEMultipart('mixed', None, [s])
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
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
        m = utils.decrypted_message_from_file(io.StringIO(m.as_string()))
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
        mail = EmailMessage()
        self._set_basic_headers(mail)
        mail.set_content('This is an email')
        actual = utils.extract_body(mail)

        expected = 'This is an email\n'

        self.assertEqual(actual, expected)

    @unittest.expectedFailure
    # This makes no sense
    def test_two_text_plain(self):
        mail = email.mime.multipart.MIMEMultipart()
        self._set_basic_headers(mail)
        mail.attach(email.mime.text.MIMEText('This is an email'))
        mail.attach(email.mime.text.MIMEText('This is a second part'))

        actual = utils.extract_body(mail)
        expected = 'This is an email\n\nThis is a second part'

        self.assertEqual(actual, expected)

    def test_text_plain_with_attachment_text(self):
        mail = EmailMessage()
        self._set_basic_headers(mail)
        mail.set_content('This is an email')
        mail.add_attachment('this shouldnt be displayed')

        actual = utils.extract_body(mail)
        expected = 'This is an email\n'

        self.assertEqual(actual, expected)

    def _make_mixed_plain_html(self):

        mail = EmailMessage()
        self._set_basic_headers(mail)
        mail.set_content('This is an email')
        mail.add_alternative(
            '<!DOCTYPE html><html><body>This is an html email</body></html>',
            subtype='html')
        return mail

    @mock.patch('alot.db.utils.settings.get', mock.Mock(return_value=True))
    def test_prefer_plaintext(self):
        expected = 'This is an email\n'
        mail = self._make_mixed_plain_html()
        actual = utils.extract_body(mail)

        self.assertEqual(actual, expected)

    # Mock the handler to cat, so that no transformations of the html are made
    # making the result non-deterministic
    @mock.patch('alot.db.utils.settings.get', mock.Mock(return_value=False))
    @mock.patch('alot.db.utils.settings.mailcap_find_match',
                mock.Mock(return_value=(None, {'view': 'cat'})))
    def test_prefer_html(self):
        expected = '<!DOCTYPE html><html><body>This is an html email</body></html>\n'
        mail = self._make_mixed_plain_html()
        actual = utils.extract_body(mail)

        self.assertEqual(actual, expected)

    def test_simple_utf8_file(self):
        mail = email.message_from_binary_file(
                open('tests/static/mail/utf8.eml', 'rb'),
                _class=email.message.EmailMessage)
        actual = utils.extract_body(mail)
        expected = "Liebe Grüße!\n"
        self.assertEqual(actual, expected)

class TestMessageFromString(unittest.TestCase):

    """Tests for decrypted_message_from_string.

    Because the implementation is that this is a wrapper around
    decrypted_message_from_file, it's not important to have a large swath of
    tests, just enough to show that things are being passed correctly.
    """

    def test(self):
        m = email.mime.text.MIMEText(u'This is some text', 'plain', 'utf-8')
        m['Subject'] = 'test'
        m['From'] = 'me'
        m['To'] = 'Nobody'
        message = utils.decrypted_message_from_string(m.as_string())
        self.assertEqual(message.get_payload(), 'This is some text')


class TestRemoveCte(unittest.TestCase):

    def test_char_vs_cte_mismatch(self):  # #1291
        with open('tests/static/mail/broken-utf8.eml') as fp:
            mail = email.message_from_file(fp)
        # This should not raise an UnicodeDecodeError.
        with self.assertLogs(level='DEBUG') as cm:  # keep logs
            utils.remove_cte(mail, as_string=True)
        # We expect no Exceptions but a complaint in the log
        logmsg = 'DEBUG:root:Decoding failure: \'utf-8\' codec can\'t decode '\
            'byte 0xa1 in position 14: invalid start byte'
        self.assertIn(logmsg, cm.output)

    def test_malformed_cte_value(self):
        with open('tests/static/mail/malformed-header-CTE.eml') as fp:
            mail = email.message_from_file(fp)

        with self.assertLogs(level='INFO') as cm:  # keep logs
            utils.remove_cte(mail, as_string=True)

        # We expect no Exceptions but a complaint in the log
        logmsg = 'INFO:root:Unknown Content-Transfer-Encoding: "7bit;"'
        self.assertEqual(cm.output, [logmsg])

    def test_unknown_cte_value(self):
        with open('tests/static/mail/malformed-header-CTE-2.eml') as fp:
            mail = email.message_from_file(fp)

        with self.assertLogs(level='DEBUG') as cm:  # keep logs
            utils.remove_cte(mail, as_string=True)

        # We expect no Exceptions but a complaint in the log
        logmsg = 'DEBUG:root:failed to interpret Content-Transfer-Encoding: '\
                 '"normal"'
        self.assertIn(logmsg, cm.output)


class Test_ensure_unique_address(unittest.TestCase):

    foo = 'foo <foo@example.com>'
    foo2 = 'foo the fanzy <foo@example.com>'
    bar = 'bar <bar@example.com>'
    baz = 'baz <baz@example.com>'

    def test_unique_lists_are_unchanged(self):
        expected = sorted([self.foo, self.bar])
        actual = utils.ensure_unique_address(expected)
        self.assertListEqual(actual, expected)

    def test_equal_entries_are_detected(self):
        actual = utils.ensure_unique_address(
            [self.foo, self.bar, self.foo])
        expected = sorted([self.foo, self.bar])
        self.assertListEqual(actual, expected)

    def test_same_address_with_different_name_is_detected(self):
        actual = utils.ensure_unique_address(
            [self.foo, self.foo2])
        expected = [self.foo2]
        self.assertListEqual(actual, expected)


class _AccountTestClass(Account):
    """Implements stubs for ABC methods."""

    def send_mail(self, mail):
        pass


class TestClearMyAddress(unittest.TestCase):

    me1 = u'me@example.com'
    me2 = u'ME@example.com'
    me3 = u'me+label@example.com'
    me4 = u'ME+label@example.com'
    me_regex = r'me\+.*@example.com'
    me_named = u'alot team <me@example.com>'
    you = u'you@example.com'
    named = u'somebody you know <somebody@example.com>'
    imposter = u'alot team <imposter@example.com>'
    mine = _AccountTestClass(
        address=me1, aliases=[], alias_regexp=me_regex, case_sensitive_username=True)


    def test_empty_input_returns_empty_list(self):
        self.assertListEqual(
            utils.clear_my_address(self.mine, []), [])

    def test_only_my_emails_result_in_empty_list(self):
        expected = []
        actual = utils.clear_my_address(
            self.mine, [self.me1, self.me3, self.me_named])
        self.assertListEqual(actual, expected)

    def test_other_emails_are_untouched(self):
        input_ = [self.you, self.me1, self.me_named, self.named]
        expected = [self.you, self.named]
        actual = utils.clear_my_address(self.mine, input_)
        self.assertListEqual(actual, expected)

    def test_case_matters(self):
        input_ = [self.me1, self.me2, self.me3, self.me4]
        expected = [self.me2, self.me4]
        actual = utils.clear_my_address(self.mine, input_)
        self.assertListEqual(actual, expected)

    def test_same_address_with_different_real_name_is_removed(self):
        input_ = [self.me_named, self.you]
        expected = [self.you]
        actual = utils.clear_my_address(self.mine, input_)
        self.assertListEqual(actual, expected)


class TestFormataddr(unittest.TestCase):

    address = u'me@example.com'
    umlauts_and_comma = '"Ö, Ä" <a@b.c>'

    def test_is_inverse(self):
        self.assertEqual(
                utils.formataddr(email.utils.parseaddr(self.umlauts_and_comma)),
                self.umlauts_and_comma
                )

    def test_address_only(self):
        self.assertEqual(utils.formataddr(("", self.address)), self.address)

    def test_name_and_address_no_comma(self):
        self.assertEqual(
                utils.formataddr(("Me", self.address)),
                "Me <me@example.com>"
                )
    def test_name_and_address_with_comma(self):
        self.assertEqual(
                utils.formataddr(("Last, Name", self.address)),
                "\"Last, Name\" <me@example.com>"
                )
