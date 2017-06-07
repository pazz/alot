# encoding=utf-8
# Copyright © 2017 Dylan Baker
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

from __future__ import absolute_import
import unittest

from alot import account


class _AccountTestClass(account.Account):
    """Implements stubs for ABC methods."""

    def send_mail(self, mail):
        pass


class TestAccount(unittest.TestCase):
    """Tests for the Account class."""

    def test_get_address(self):
        """Tests address without aliases."""
        acct = _AccountTestClass(address=u"foo@example.com")
        self.assertListEqual(acct.get_addresses(), [u'foo@example.com'])

    def test_get_address_with_aliases(self):
        """Tests address with aliases."""
        acct = _AccountTestClass(address=u"foo@example.com",
                                 aliases=[u'bar@example.com'])
        self.assertListEqual(acct.get_addresses(),
                             [u'foo@example.com', u'bar@example.com'])

    def test_deprecated_encrypt_by_default(self):
        """Tests that depreacted values are still accepted."""
        for each in [u'true', u'yes', u'1']:
            acct = _AccountTestClass(address=u'foo@example.com',
                                     encrypt_by_default=each)
            self.assertEqual(acct.encrypt_by_default, u'all')
        for each in [u'false', u'no', u'0']:
            acct = _AccountTestClass(address=u'foo@example.com',
                                     encrypt_by_default=each)
            self.assertEqual(acct.encrypt_by_default, u'none')
