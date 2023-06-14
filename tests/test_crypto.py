# Copyright (C) 2017 Lucas Hoffmann
# Copyright © 2017-2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os
import shutil
import signal
import subprocess
import tempfile
import unittest
from unittest import mock

import gpg
import urwid

from alot import crypto
from alot.errors import GPGProblem, GPGCode

from . import utilities


MOD_CLEAN = utilities.ModuleCleanup()

# A useful single fingerprint for tests that only care about one key. This
# key will not be ambiguous
FPR = "F74091D4133F87D56B5D343C1974EC55FBC2D660"

# Some additional keys, these keys may be ambigiuos
EXTRA_FPRS = [
    "DD19862809A7573A74058FF255937AFBB156245D",
    "2071E9C8DB4EF5466F4D233CF730DF92C4566CE7",
]

DEVNULL = open('/dev/null', 'w')
MOD_CLEAN.add_cleanup(DEVNULL.close)


@MOD_CLEAN.wrap_setup
def setUpModule():
    home = tempfile.mkdtemp()
    MOD_CLEAN.add_cleanup(shutil.rmtree, home)
    mock_home = mock.patch.dict(os.environ, {'GNUPGHOME': home})
    mock_home.start()
    MOD_CLEAN.add_cleanup(mock_home.stop)

    with gpg.core.Context(armor=True) as ctx:
        # Add the public and private keys. They have no password
        search_dir = os.path.join(os.path.dirname(__file__), 'static/gpg-keys')
        for each in os.listdir(search_dir):
            if os.path.splitext(each)[1] == '.gpg':
                with open(os.path.join(search_dir, each)) as f:
                    ctx.op_import(f)


@MOD_CLEAN.wrap_teardown
def tearDownModule():
    # Kill any gpg-agent's that have been opened
    lookfor = 'gpg-agent --homedir {}'.format(os.environ['GNUPGHOME'])

    out = subprocess.check_output(
        ['ps', 'xo', 'pid,cmd'],
        stderr=DEVNULL).decode(urwid.util.detected_encoding)
    for each in out.strip().split('\n'):
        pid, cmd = each.strip().split(' ', 1)
        if cmd.startswith(lookfor):
            os.kill(int(pid), signal.SIGKILL)


def make_key(revoked=False, expired=False, invalid=False, can_encrypt=True,
             can_sign=True):
    # This is ugly
    mock_key = mock.create_autospec(gpg._gpgme._gpgme_key)
    mock_key.uids = [mock.Mock(uid='mocked')]
    mock_key.revoked = revoked
    mock_key.expired = expired
    mock_key.invalid = invalid
    mock_key.can_encrypt = can_encrypt
    mock_key.can_sign = can_sign

    return mock_key


def make_uid(email, revoked=False, invalid=False,
             validity=gpg.constants.validity.FULL):
    uid = mock.Mock()
    uid.email = email
    uid.revoked = revoked
    uid.invalid = invalid
    uid.validity = validity

    return uid


class TestHashAlgorithmHelper(unittest.TestCase):

    """Test cases for the helper function RFC3156_canonicalize."""

    def test_returned_string_starts_with_pgp(self):
        result = crypto.RFC3156_micalg_from_algo(gpg.constants.md.MD5)
        self.assertTrue(result.startswith('pgp-'))

    def test_returned_string_is_lower_case(self):
        result = crypto.RFC3156_micalg_from_algo(gpg.constants.md.MD5)
        self.assertTrue(result.islower())

    def test_raises_for_unknown_hash_name(self):
        with self.assertRaises(GPGProblem):
            crypto.RFC3156_micalg_from_algo(gpg.constants.md.NONE)


class TestDetachedSignatureFor(unittest.TestCase):

    def test_valid_signature_generated(self):
        to_sign = b"this is some text.\nit is more than nothing.\n"
        with gpg.core.Context() as ctx:
            _, detached = crypto.detached_signature_for(
                to_sign, [ctx.get_key(FPR)])

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(detached)
            sig = f.name
        self.addCleanup(os.unlink, f.name)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(to_sign)
            text = f.name
        self.addCleanup(os.unlink, f.name)

        res = subprocess.check_call(['gpg', '--verify', sig, text],
                                    stdout=DEVNULL, stderr=DEVNULL)
        self.assertEqual(res, 0)


class TestVerifyDetached(unittest.TestCase):

    def test_verify_signature_good(self):
        to_sign = b"this is some text.\nIt's something\n."
        with gpg.core.Context() as ctx:
            _, detached = crypto.detached_signature_for(
                to_sign, [ctx.get_key(FPR)])

        try:
            crypto.verify_detached(to_sign, detached)
        except GPGProblem:
            raise AssertionError

    def test_verify_signature_bad(self):
        to_sign = b"this is some text.\nIt's something\n."
        similar = b"this is some text.\r\n.It's something\r\n."
        with gpg.core.Context() as ctx:
            _, detached = crypto.detached_signature_for(
                to_sign, [ctx.get_key(FPR)])

        with self.assertRaises(GPGProblem):
            crypto.verify_detached(similar, detached)


class TestValidateKey(unittest.TestCase):

    def test_valid(self):
        try:
            crypto.validate_key(utilities.make_key())
        except GPGProblem as e:
            raise AssertionError(e)

    def test_revoked(self):
        with self.assertRaises(GPGProblem) as caught:
            crypto.validate_key(utilities.make_key(revoked=True))

        self.assertEqual(caught.exception.code, GPGCode.KEY_REVOKED)

    def test_expired(self):
        with self.assertRaises(GPGProblem) as caught:
            crypto.validate_key(utilities.make_key(expired=True))

        self.assertEqual(caught.exception.code, GPGCode.KEY_EXPIRED)

    def test_invalid(self):
        with self.assertRaises(GPGProblem) as caught:
            crypto.validate_key(utilities.make_key(invalid=True))

        self.assertEqual(caught.exception.code, GPGCode.KEY_INVALID)

    def test_encrypt(self):
        with self.assertRaises(GPGProblem) as caught:
            crypto.validate_key(
                utilities.make_key(can_encrypt=False), encrypt=True)

        self.assertEqual(caught.exception.code, GPGCode.KEY_CANNOT_ENCRYPT)

    def test_encrypt_no_check(self):
        try:
            crypto.validate_key(utilities.make_key(can_encrypt=False))
        except GPGProblem as e:
            raise AssertionError(e)

    def test_sign(self):
        with self.assertRaises(GPGProblem) as caught:
            crypto.validate_key(utilities.make_key(can_sign=False), sign=True)

        self.assertEqual(caught.exception.code, GPGCode.KEY_CANNOT_SIGN)

    def test_sign_no_check(self):
        try:
            crypto.validate_key(utilities.make_key(can_sign=False))
        except GPGProblem as e:
            raise AssertionError(e)


class TestCheckUIDValidity(unittest.TestCase):

    def test_valid_single(self):
        key = utilities.make_key()
        key.uids[0] = utilities.make_uid(mock.sentinel.EMAIL)
        ret = crypto.check_uid_validity(key, mock.sentinel.EMAIL)
        self.assertTrue(ret)

    def test_valid_multiple(self):
        key = utilities.make_key()
        key.uids = [
            utilities.make_uid(mock.sentinel.EMAIL),
            utilities.make_uid(mock.sentinel.EMAIL1),
        ]

        ret = crypto.check_uid_validity(key, mock.sentinel.EMAIL1)
        self.assertTrue(ret)

    def test_invalid_email(self):
        key = utilities.make_key()
        key.uids[0] = utilities.make_uid(mock.sentinel.EMAIL)
        ret = crypto.check_uid_validity(key, mock.sentinel.EMAIL1)
        self.assertFalse(ret)

    def test_invalid_revoked(self):
        key = utilities.make_key()
        key.uids[0] = utilities.make_uid(mock.sentinel.EMAIL, revoked=True)
        ret = crypto.check_uid_validity(key, mock.sentinel.EMAIL)
        self.assertFalse(ret)

    def test_invalid_invalid(self):
        key = utilities.make_key()
        key.uids[0] = utilities.make_uid(mock.sentinel.EMAIL, invalid=True)
        ret = crypto.check_uid_validity(key, mock.sentinel.EMAIL)
        self.assertFalse(ret)

    def test_invalid_not_enough_trust(self):
        key = utilities.make_key()
        key.uids[0] = utilities.make_uid(
            mock.sentinel.EMAIL,
            validity=gpg.constants.validity.UNDEFINED)
        ret = crypto.check_uid_validity(key, mock.sentinel.EMAIL)
        self.assertFalse(ret)


class TestListKeys(unittest.TestCase):

    def test_list_no_hints(self):
        # This only tests that you get 3 keys back (the number in our test
        # keyring), it might be worth adding tests to check more about the keys
        # returned
        values = crypto.list_keys()
        self.assertEqual(len(list(values)), 3)

    def test_list_hint(self):
        values = crypto.list_keys(hint="ambig")
        self.assertEqual(len(list(values)), 2)

    def test_list_keys_pub(self):
        values = list(crypto.list_keys(hint="ambigu"))[0]
        self.assertEqual(values.uids[0].email, 'amigbu@example.com')
        self.assertFalse(values.secret)

    def test_list_keys_private(self):
        values = list(crypto.list_keys(hint="ambigu", private=True))[0]
        self.assertEqual(values.uids[0].email, 'amigbu@example.com')
        self.assertTrue(values.secret)


class TestGetKey(unittest.TestCase):

    def test_plain(self):
        # Test the uid of the only identity attached to the key we generated.
        with gpg.core.Context() as ctx:
            expected = ctx.get_key(FPR).uids[0].uid
        actual = crypto.get_key(FPR).uids[0].uid
        self.assertEqual(expected, actual)

    def test_validate(self):
        # Since we already test validation we're only going to test validate
        # once.
        with gpg.core.Context() as ctx:
            expected = ctx.get_key(FPR).uids[0].uid
        actual = crypto.get_key(
            FPR, validate=True, encrypt=True, sign=True).uids[0].uid
        self.assertEqual(expected, actual)

    def test_missing_key(self):
        with self.assertRaises(GPGProblem) as caught:
            crypto.get_key('foo@example.com')
        self.assertEqual(caught.exception.code, GPGCode.NOT_FOUND)

    def test_invalid_key(self):
        with self.assertRaises(GPGProblem) as caught:
            crypto.get_key('z')
        self.assertEqual(caught.exception.code, GPGCode.NOT_FOUND)

    @mock.patch('alot.crypto.check_uid_validity', mock.Mock(return_value=True))
    def test_signed_only_true(self):
        try:
            crypto.get_key(FPR, signed_only=True)
        except GPGProblem as e:
            raise AssertionError(e)

    @mock.patch(
        'alot.crypto.check_uid_validity', mock.Mock(return_value=False))
    def test_signed_only_false(self):
        with self.assertRaises(GPGProblem) as e:
            crypto.get_key(FPR, signed_only=True)
        self.assertEqual(e.exception.code, GPGCode.NOT_FOUND)

    @staticmethod
    def _context_mock():
        class CustomError(gpg.errors.GPGMEError):
            """A custom GPGMEError class that always has an errors code of
            AMBIGUOUS_NAME.
            """
            def getcode(self):
                return gpg.errors.AMBIGUOUS_NAME

        context_mock = mock.Mock()
        context_mock.get_key = mock.Mock(side_effect=CustomError)

        return context_mock

    def test_ambiguous_one_valid(self):
        invalid_key = utilities.make_key(invalid=True)
        valid_key = utilities.make_key()

        with mock.patch('alot.crypto.gpg.core.Context',
                        mock.Mock(return_value=self._context_mock())), \
                mock.patch('alot.crypto.list_keys',
                           mock.Mock(return_value=[valid_key, invalid_key])):
            key = crypto.get_key('placeholder')
        self.assertIs(key, valid_key)

    def test_ambiguous_two_valid(self):
        with mock.patch('alot.crypto.gpg.core.Context',
                        mock.Mock(return_value=self._context_mock())), \
                mock.patch('alot.crypto.list_keys',
                           mock.Mock(return_value=[utilities.make_key(),
                                                   utilities.make_key()])):
            with self.assertRaises(crypto.GPGProblem) as cm:
                crypto.get_key('placeholder')
        self.assertEqual(cm.exception.code, GPGCode.AMBIGUOUS_NAME)

    def test_ambiguous_no_valid(self):
        with mock.patch('alot.crypto.gpg.core.Context',
                        mock.Mock(return_value=self._context_mock())), \
                mock.patch('alot.crypto.list_keys',
                           mock.Mock(return_value=[
                               utilities.make_key(invalid=True),
                               utilities.make_key(invalid=True)])):
            with self.assertRaises(crypto.GPGProblem) as cm:
                crypto.get_key('placeholder')
        self.assertEqual(cm.exception.code, GPGCode.NOT_FOUND)


class TestEncrypt(unittest.TestCase):

    def test_encrypt(self):
        to_encrypt = b"this is a string\nof data."
        encrypted = crypto.encrypt(to_encrypt, keys=[crypto.get_key(FPR)])

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(encrypted)
            enc_file = f.name
        self.addCleanup(os.unlink, enc_file)

        dec = subprocess.check_output(
            ['gpg', '--decrypt', enc_file], stderr=DEVNULL)
        self.assertEqual(to_encrypt, dec)


class TestDecrypt(unittest.TestCase):

    def test_decrypt(self):
        to_encrypt = b"this is a string\nof data."
        encrypted = crypto.encrypt(to_encrypt, keys=[crypto.get_key(FPR)])
        _, dec = crypto.decrypt_verify(encrypted)
        self.assertEqual(to_encrypt, dec)

    # TODO: test for "combined" method
