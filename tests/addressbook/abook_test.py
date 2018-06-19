# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os
import tempfile
import unittest

from alot.addressbook import abook
from alot.settings.errors import ConfigError


class TestAbookAddressBook(unittest.TestCase):

    def test_abook_file_can_not_be_empty(self):
        with self.assertRaises(ConfigError):
            abook.AbookAddressBook("/dev/null")

    def test_get_contacts_lists_all_emails(self):
        data = """
        [format]
        version = unknown
        program = alot-test-suite
        [1]
        name = me
        email = me@example.com
        [2]
        name = you
        email = you@other.domain, you@example.com
        """
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
            self.addCleanup(os.unlink, path)
        addressbook = abook.AbookAddressBook(path)
        actual = addressbook.get_contacts()
        expected = [('me', 'me@example.com'), ('you', 'you@other.domain'),
                    ('you', 'you@example.com')]
        self.assertListEqual(actual, expected)
