# Copyright (C) 2017 Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import os
import shutil
import subprocess
import tempfile
import unittest

import gpgme
import mock

from . import utilities

from alot import crypto
from alot.errors import GPGProblem


class TestHashAlgorithmHelper(unittest.TestCase):

    """Test cases for the helper function RFC3156_canonicalize."""

    def test_returned_string_starts_with_pgp(self):
        result = crypto.RFC3156_micalg_from_algo(gpgme.MD_MD5)
        self.assertTrue(result.startswith('pgp-'))

    def test_returned_string_is_lower_case(self):
        result = crypto.RFC3156_micalg_from_algo(gpgme.MD_MD5)
        self.assertTrue(result.islower())

    def test_raises_for_unknown_hash_name(self):
        with self.assertRaises(GPGProblem):
            crypto.RFC3156_micalg_from_algo(gpgme.MD_NONE)


class TestSignature(utilities.TestCaseClassCleanup):

    FPR = "F74091D4133F87D56B5D343C1974EC55FBC2D660"

    @classmethod
    def setUpClass(cls):
        # Create a temporary directory to use as gnupg's home directory. This
        # allows us to import keys without dirtying the user's keyring
        home = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, home)
        mock_home = mock.patch.dict(os.environ, {'GNUPGHOME': home})
        mock_home.start()
        cls.addClassCleanup(mock_home.stop)

        # create a single context to use class wide.
        cls.ctx = gpgme.Context()
        cls.ctx.armor = True

        # Add the public and private keys. They have no password
        here = os.path.dirname(__file__)
        with open(os.path.join(here, 'static/pub.gpg')) as f:
            cls.ctx.import_(f)
        with open(os.path.join(here, 'static/sec.gpg')) as f:
            cls.ctx.import_(f)

        cls.key = cls.ctx.get_key(cls.FPR)

    def test_detached_signature_for(self):
        to_sign = "this is some text.\nit is more than nothing.\n"
        _, detached = crypto.detached_signature_for(to_sign, self.key)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(detached)
            sig = f.name
        self.addCleanup(os.unlink, f.name)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(to_sign)
            text = f.name
        self.addCleanup(os.unlink, f.name)

        res = subprocess.check_call(['gpg', '--verify', sig, text])
        self.assertEqual(res, 0)

    def test_verify_signature_good(self):
        to_sign = "this is some text.\nIt's something\n."
        _, detached = crypto.detached_signature_for(to_sign, self.key)

        try:
            crypto.verify_detached(to_sign, detached)
        except GPGProblem:
            raise AssertionError

    def test_verify_signature_bad(self):
        to_sign = "this is some text.\nIt's something\n."
        similar = "this is some text.\r\n.It's something\r\n."
        _, detached = crypto.detached_signature_for(to_sign, self.key)

        with self.assertRaises(GPGProblem):
            crypto.verify_detached(similar, detached)
