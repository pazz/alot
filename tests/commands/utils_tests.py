# encoding=utf-8
# Copyright © 2017-2018 Dylan Baker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import tempfile
import os
import shutil
import unittest
from unittest import mock

import gpg

from alot import crypto
from alot import errors
from alot.commands import utils
from alot.db.envelope import Envelope

from .. import utilities

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
        search_dir = os.path.join(
            os.path.dirname(__file__), '../static/gpg-keys')
        for each in os.listdir(search_dir):
            if os.path.splitext(each)[1] == '.gpg':
                with open(os.path.join(search_dir, each)) as f:
                    ctx.op_import(f)


@MOD_CLEAN.wrap_teardown
def tearDownModule():
    pass


class TestGetKeys(unittest.TestCase):

    # pylint: disable=protected-access

    @utilities.async_test
    async def test_get_keys(self):
        """Test that getting keys works when all keys are present."""
        expected = crypto.get_key(FPR, validate=True, encrypt=True,
                                  signed_only=False)
        ui = utilities.make_ui()
        ids = [FPR]
        actual = await utils._get_keys(ui, ids)
        self.assertIn(FPR, actual)
        self.assertEqual(actual[FPR].fpr, expected.fpr)

    @utilities.async_test
    async def test_get_keys_missing(self):
        """Test that getting keys works when some keys are missing."""
        expected = crypto.get_key(FPR, validate=True, encrypt=True,
                                  signed_only=False)
        ui = utilities.make_ui()
        ids = [FPR, "6F6B15509CF8E59E6E469F327F438280EF8D349F"]
        actual = await utils._get_keys(ui, ids)
        self.assertIn(FPR, actual)
        self.assertEqual(actual[FPR].fpr, expected.fpr)

    @utilities.async_test
    async def test_get_keys_signed_only(self):
        """Test gettings keys when signed only is required."""
        ui = utilities.make_ui()
        ids = [FPR]
        actual = await utils._get_keys(ui, ids, signed_only=True)
        self.assertEqual(actual, {})

    @utilities.async_test
    async def test_get_keys_ambiguous(self):
        """Test gettings keys when when the key is ambiguous."""
        key = crypto.get_key(
            FPR, validate=True, encrypt=True, signed_only=False)
        ui = utilities.make_ui()

        # Creat a ui.choice object that can satisfy asyncio, but can also be
        # queried for calls as a mock
        async def choice(*args, **kwargs):
            return None
        ui.choice = mock.Mock(wraps=choice)

        ids = [FPR]
        with mock.patch('alot.commands.utils.crypto.get_key',
                        mock.Mock(side_effect=errors.GPGProblem(
                            'test', errors.GPGCode.AMBIGUOUS_NAME))):
            with mock.patch('alot.commands.utils.crypto.list_keys',
                            mock.Mock(return_value=[key])):
                await utils._get_keys(ui, ids, signed_only=False)
        ui.choice.assert_called_once()


class _Account(object):
    def __init__(self, encrypt_to_self=True, gpg_key=None):
        self.encrypt_to_self = encrypt_to_self
        self.gpg_key = gpg_key


class TestSetEncrypt(unittest.TestCase):

    @utilities.async_test
    async def test_get_keys_from_to(self):
        ui = utilities.make_ui()
        envelope = Envelope()
        envelope['To'] = 'ambig@example.com, test@example.com'
        await utils.update_keys(ui, envelope)
        self.assertTrue(envelope.encrypt)
        self.assertCountEqual(
            [f.fpr for f in envelope.encrypt_keys.values()],
            [crypto.get_key(FPR).fpr, crypto.get_key(EXTRA_FPRS[0]).fpr])

    @utilities.async_test
    async def test_get_keys_from_cc(self):
        ui = utilities.make_ui()
        envelope = Envelope()
        envelope['Cc'] = 'ambig@example.com, test@example.com'
        await utils.update_keys(ui, envelope)
        self.assertTrue(envelope.encrypt)
        self.assertCountEqual(
            [f.fpr for f in envelope.encrypt_keys.values()],
            [crypto.get_key(FPR).fpr, crypto.get_key(EXTRA_FPRS[0]).fpr])

    @utilities.async_test
    async def test_get_partial_keys(self):
        ui = utilities.make_ui()
        envelope = Envelope()
        envelope['Cc'] = 'foo@example.com, test@example.com'
        await utils.update_keys(ui, envelope)
        self.assertTrue(envelope.encrypt)
        self.assertCountEqual(
            [f.fpr for f in envelope.encrypt_keys.values()],
            [crypto.get_key(FPR).fpr])

    @utilities.async_test
    async def test_get_no_keys(self):
        ui = utilities.make_ui()
        envelope = Envelope()
        envelope['To'] = 'foo@example.com'
        await utils.update_keys(ui, envelope)
        self.assertFalse(envelope.encrypt)
        self.assertEqual(envelope.encrypt_keys, {})

    @utilities.async_test
    async def test_encrypt_to_self_true(self):
        ui = utilities.make_ui()
        envelope = Envelope()
        envelope['From'] = 'test@example.com'
        envelope['To'] = 'ambig@example.com'
        gpg_key = crypto.get_key(FPR)
        account = _Account(encrypt_to_self=True, gpg_key=gpg_key)
        envelope.account = account
        await utils.update_keys(ui, envelope)
        self.assertTrue(envelope.encrypt)
        self.assertIn(FPR, envelope.encrypt_keys)
        self.assertEqual(gpg_key, envelope.encrypt_keys[FPR])

    @utilities.async_test
    async def test_encrypt_to_self_false(self):
        ui = utilities.make_ui()
        envelope = Envelope()
        envelope['From'] = 'test@example.com'
        envelope['To'] = 'ambig@example.com'
        gpg_key = crypto.get_key(FPR)
        account = _Account(encrypt_to_self=False, gpg_key=gpg_key)
        envelope.account = account
        await utils.update_keys(ui, envelope)
        self.assertTrue(envelope.encrypt)
        self.assertNotIn(FPR, envelope.encrypt_keys)
