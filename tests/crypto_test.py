# Copyright (C) 2017 Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import unittest

import gpgme

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
