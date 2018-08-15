# Copyright © 2017 Lucas Hoffmann
# Copyright © 2018 Dylan Baker
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

import email.parser
import email.policy
import os
import tempfile
import unittest
from unittest import mock

from alot.db import envelope

SETTINGS = {
    'user_agent': 'agent',
}


def email_to_dict(mail):
    """Consumes an email, and returns a dict of headers and 'Body'."""
    split = mail.splitlines()
    final = {}
    for line in split:
        if line.strip():
            try:
                k, v = line.split(':')
                final[k.strip()] = v.strip()
            except ValueError:
                final['Body'] = line.strip()
    return final


class TestEnvelope(unittest.TestCase):

    def assertEmailEqual(self, first, second):
        with self.subTest('body'):
            self.assertEqual(first.is_multipart(), second.is_multipart())
            if not first.is_multipart():
                self.assertEqual(first.get_payload(), second.get_payload())
            else:
                for f, s in zip(first.walk(), second.walk()):
                    if f.is_multipart() or s.is_multipart():
                        self.assertEqual(first.is_multipart(),
                                         second.is_multipart())
                    else:
                        self.assertEqual(f.get_payload(), s.get_payload())
        with self.subTest('headers'):
            self.assertListEqual(first.values(), second.values())

    def test_setitem_stores_text_unchanged(self):
        "Just ensure that the value is set and unchanged"
        e = envelope.Envelope()
        e['Subject'] = u'sm\xf8rebr\xf8d'
        self.assertEqual(e['Subject'], u'sm\xf8rebr\xf8d')

    def _test_mail(self, envelope):
        mail = envelope.construct_mail()
        raw = mail.as_string(policy=email.policy.SMTP)
        actual = email.parser.Parser().parsestr(raw)
        self.assertEmailEqual(mail, actual)

    @mock.patch('alot.db.envelope.settings', SETTINGS)
    def test_construct_mail_simple(self):
        """Very simple envelope with a To, From, Subject, and body."""
        headers = {
            'From': 'foo@example.com',
            'To': 'bar@example.com',
            'Subject': 'Test email',
        }
        e = envelope.Envelope(headers={k: [v] for k, v in headers.items()},
                              bodytext='Test')
        self._test_mail(e)

    @mock.patch('alot.db.envelope.settings', SETTINGS)
    def test_construct_mail_with_attachment(self):
        """Very simple envelope with a To, From, Subject, body and attachment.
        """
        headers = {
            'From': 'foo@example.com',
            'To': 'bar@example.com',
            'Subject': 'Test email',
        }
        e = envelope.Envelope(headers={k: [v] for k, v in headers.items()},
                              bodytext='Test')
        with tempfile.NamedTemporaryFile(mode='wt', delete=False) as f:
            f.write('blah')
        self.addCleanup(os.unlink, f.name)
        e.attach(f.name)

        self._test_mail(e)
