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
        acct = _AccountTestClass(address="foo@example.com")
        self.assertListEqual(acct.get_addresses(), ['foo@example.com'])

    def test_get_address_with_aliases(self):
        """Tests address with aliases."""
        acct = _AccountTestClass(address="foo@example.com",
                                 aliases=['bar@example.com'])
        self.assertListEqual(acct.get_addresses(),
                             ['foo@example.com', 'bar@example.com'])

    def test_deprecated_encrypt_by_default(self):
        """Tests that depreacted values are still accepted."""
        for each in ['true', 'yes', '1']:
            acct = _AccountTestClass(address='foo@example.com',
                                     encrypt_by_default=each)
            self.assertEqual(acct.encrypt_by_default, 'all')
        for each in ['false', 'no', '0']:
            acct = _AccountTestClass(address='foo@example.com',
                                     encrypt_by_default=each)
            self.assertEqual(acct.encrypt_by_default, 'none')


class TestAddress(unittest.TestCase):

    """Tests for the Address class."""

    def test_constructor_bytes(self):
        with self.assertRaises(AssertionError):
            account.Address(b'username', b'domainname')

    def test_from_string_bytes(self):
        with self.assertRaises(AssertionError):
            account.Address.from_string(b'user@example.com')

    def test_from_string(self):
        addr = account.Address.from_string('user@example.com')
        self.assertEqual(addr.username, 'user')
        self.assertEqual(addr.domainname, 'example.com')

    def test_str(self):
        addr = account.Address('ušer', 'example.com')
        self.assertEqual(str(addr), 'ušer@example.com')

    def test_bytes(self):
        addr = account.Address('ušer', 'example.com')
        self.assertEqual(bytes(addr), 'ušer@example.com'.encode('utf-8'))

    def test_eq_unicode(self):
        addr = account.Address('ušer', 'example.com')
        self.assertEqual(addr, 'ušer@example.com')

    def test_eq_address(self):
        addr = account.Address('ušer', 'example.com')
        addr2 = account.Address('ušer', 'example.com')
        self.assertEqual(addr, addr2)

    def test_ne_unicode(self):
        addr = account.Address('ušer', 'example.com')
        self.assertNotEqual(addr, 'user@example.com')

    def test_ne_address(self):
        addr = account.Address('ušer', 'example.com')
        addr2 = account.Address('user', 'example.com')
        self.assertNotEqual(addr, addr2)

    def test_eq_unicode_case(self):
        addr = account.Address('UŠer', 'example.com')
        self.assertEqual(addr, 'ušer@example.com')

    def test_ne_unicode_case(self):
        addr = account.Address('ušer', 'example.com')
        self.assertEqual(addr, 'uŠer@example.com')

    def test_ne_address_case(self):
        addr = account.Address('ušer', 'example.com')
        addr2 = account.Address('uŠer', 'example.com')
        self.assertEqual(addr, addr2)

    def test_eq_address_case(self):
        addr = account.Address('UŠer', 'example.com')
        addr2 = account.Address('ušer', 'example.com')
        self.assertEqual(addr, addr2)

    def test_eq_unicode_case_sensitive(self):
        addr = account.Address('UŠer', 'example.com', case_sensitive=True)
        self.assertNotEqual(addr, 'ušer@example.com')

    def test_eq_address_case_sensitive(self):
        addr = account.Address('UŠer', 'example.com', case_sensitive=True)
        addr2 = account.Address('ušer', 'example.com')
        self.assertNotEqual(addr, addr2)

    def test_eq_str(self):
        addr = account.Address('user', 'example.com', case_sensitive=True)
        with self.assertRaises(TypeError):
            addr == 1  # pylint: disable=pointless-statement

    def test_ne_str(self):
        addr = account.Address('user', 'example.com', case_sensitive=True)
        with self.assertRaises(TypeError):
            addr != 1  # pylint: disable=pointless-statement

    def test_repr(self):
        addr = account.Address('user', 'example.com', case_sensitive=True)
        self.assertEqual(
            repr(addr),
            "Address('user', 'example.com', case_sensitive=True)")

    def test_domain_name_ne(self):
        addr = account.Address('user', 'example.com')
        self.assertNotEqual(addr, 'user@example.org')

    def test_domain_name_eq_case(self):
        addr = account.Address('user', 'example.com')
        self.assertEqual(addr, 'user@Example.com')

    def test_domain_name_ne_unicode(self):
        addr = account.Address('user', 'éxample.com')
        self.assertNotEqual(addr, 'user@example.com')

    def test_domain_name_eq_unicode(self):
        addr = account.Address('user', 'éxample.com')
        self.assertEqual(addr, 'user@Éxample.com')

    def test_domain_name_eq_case_sensitive(self):
        addr = account.Address('user', 'example.com', case_sensitive=True)
        self.assertEqual(addr, 'user@Example.com')

    def test_domain_name_eq_unicode_sensitive(self):
        addr = account.Address('user', 'éxample.com', case_sensitive=True)
        self.assertEqual(addr, 'user@Éxample.com')

    def test_cmp_empty(self):
        addr = account.Address('user', 'éxample.com')
        self.assertNotEqual(addr, '')
