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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import email.message
import unittest
from unittest import mock

from notmuch2 import NullPointerError

from alot import account
from alot.db import message


class MockNotmuchMessage:
    """An object that looks very much like a notmuch message.

    All public instance variables that are not part of the notmuch Message
    class are prefaced with mock.
    """

    class MockProperties:
        def getall(self, *args, **kwargs):
            return []

    def __init__(self, headers=None, tags=None):
        self.mock_headers = headers or {}
        self.mock_message_id = 'message id'
        self.mock_thread_id = 'thread id'
        self.mock_date = 0
        self.mock_filename = 'filename'
        self.mock_tags = tags or []

    def header(self, field):
        return self.mock_headers.get(field, '')

    @property
    def messageid(self):
        return self.mock_message_id

    @property
    def threadid(self):
        return self.mock_thread_id

    @property
    def date(self):
        return self.mock_date

    @property
    def path(self):
        return self.mock_filename

    @property
    def tags(self):
        return self.mock_tags

    @property
    def properties(self):
        return MockNotmuchMessage.MockProperties()


class TestMessage(unittest.TestCase):

    def test_refresh_rereads_tags(self):
        dbman = mock.MagicMock()
        msg = message.Message(dbman, MockNotmuchMessage(tags=['inbox']))
        changed = MockNotmuchMessage(tags=['inbox', 'new'])
        dbman._with_notmuch_message.return_value.__enter__.return_value = \
            changed
        msg.refresh()
        self.assertEqual(msg.get_tags(), ['inbox', 'new'])

    def test_tags_are_read_from_notmuch_once(self):
        """Iterating notmuch's tag set is slow: a thread of n messages used to
        read tags n**2 times (#694)."""
        class CountingTags:
            reads = 0

            def __iter__(self):
                CountingTags.reads += 1
                return iter(['inbox', 'unread'])

        msg = message.Message(mock.Mock(),
                              MockNotmuchMessage(tags=CountingTags()))
        for _ in range(3):
            self.assertEqual(msg.get_tags(), ['inbox', 'unread'])
        self.assertEqual(CountingTags.reads, 1)

    def test_get_subject_is_one_decoded_line(self):
        for raw, subject in [
                ('=?utf-8?q?Gr=C3=BC=C3=9Fe?= from the list',
                 'Grüße from the list'),
                ('folded\n subject', 'folded subject'),
                ('=?utf-8?q?a=0AMallory_=28Oct_01=29=3A_LGTM?=',
                 'a Mallory (Oct 01): LGTM')]:
            with self.subTest(raw=raw):
                msg = message.Message(
                    mock.Mock(), MockNotmuchMessage({'Subject': raw}))
                self.assertEqual(msg.get_subject(), subject)

    def test_get_subject_without_header(self):
        for error in (LookupError('Subject'), NullPointerError()):
            class NoSubject(MockNotmuchMessage):
                def header(self, field):
                    if field == 'Subject':
                        raise error  # as notmuch2 does
                    return super().header(field)

            with self.subTest(error=error):
                msg = message.Message(mock.Mock(), NoSubject())
                self.assertEqual(msg.get_subject(), '')

    def test_get_author_email_only(self):
        """Message._from is populated using the 'From' header when only an
        email address is provided.
        """
        msg = message.Message(mock.Mock(),
                              MockNotmuchMessage({'From': 'user@example.com'}))
        self.assertEqual(msg.get_author(), ('', 'user@example.com'))

    def test_get_author_name_and_email(self):
        """Message._from is populated using the 'From' header when an email and
        name are provided.
        """
        msg = message.Message(
            mock.Mock(),
            MockNotmuchMessage({'From': '"User Name" <user@example.com>'}))
        self.assertEqual(msg.get_author(), ('User Name', 'user@example.com'))

    def test_get_author_sender(self):
        """Message._from is populated using the 'Sender' header when no 'From'
        header is present.
        """
        msg = message.Message(
            mock.Mock(),
            MockNotmuchMessage({'Sender': '"User Name" <user@example.com>'}))
        self.assertEqual(msg.get_author(), ('User Name', 'user@example.com'))

    def test_get_author_no_name_draft(self):
        """Message._from is populated from the default account if the draft tag
        is present.
        """
        acc = mock.Mock()
        acc.address = account.Address('user', 'example.com')
        acc.realname = 'User Name'
        with mock.patch('alot.db.message.settings.get_accounts',
                        mock.Mock(return_value=[acc])):
            msg = message.Message(
                mock.Mock(), MockNotmuchMessage(tags=['draft']))
        self.assertEqual(msg.get_author(), ('User Name', 'user@example.com'))

    def test_get_author_no_name(self):
        """Message._from is set to 'Unkown' if there is no relavent header and
        the message is not a draft.
        """
        acc = mock.Mock()
        acc.address = account.Address('user', 'example.com')
        acc.realname = 'User Name'
        with mock.patch('alot.db.message.settings.get_accounts',
                        mock.Mock(return_value=[acc])):
            msg = message.Message(mock.Mock(), MockNotmuchMessage())
        self.assertEqual(msg.get_author(), ('Unknown', ''))

    def test_attachment_without_content_disposition(self):
        nm = MockNotmuchMessage()
        nm.mock_filename = 'tests/static/mail/attachment-without-disposition.eml'
        msg = message.Message(mock.Mock(), nm)
        self.assertEqual([a.get_filename() for a in msg.get_attachments()],
                         ['20328884_2013.pdf'])

    def test_selected_mime_part_without_headers_is_kept(self):
        # a part without headers, such as an implicit text/plain part,
        # has length 0 and so is false
        part = email.message.EmailMessage()
        part.set_payload('chosen')
        msg = message.Message(mock.Mock(), MockNotmuchMessage())
        msg.set_mime_part(part)
        self.assertIs(msg.get_mime_part(), part)

    def test_signature_without_content_disposition_is_no_attachment(self):
        part = email.message.Message()
        part['Content-Type'] = 'application/pgp-signature; name="signature.asc"'
        self.assertFalse(message.Message._is_attachment(part))
