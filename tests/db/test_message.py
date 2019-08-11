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

import mock

from alot import account
from alot.db import message


class MockNotmuchMessage(object):
    """An object that looks very much like a notmuch message.

    All public instance variables that are not part of the notmuch Message
    class are prefaced with mock.
    """

    def __init__(self, headers=None, tags=None):
        self.mock_headers = headers or {}
        self.mock_message_id = 'message id'
        self.mock_thread_id = 'thread id'
        self.mock_date = 0
        self.mock_filename = 'filename'
        self.mock_tags = tags or []

    def get_header(self, field):
        return self.mock_headers.get(field, '')

    def get_message_id(self):
        return self.mock_message_id

    def get_thread_id(self):
        return self.mock_thread_id

    def get_date(self):
        return self.mock_date

    def get_filename(self):
        return self.mock_filename

    def get_tags(self):
        return self.mock_tags

    def get_properties(self, prop, exact=False):
        return []


class TestMessage(unittest.TestCase):

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
        acc.address = account.Address(u'user', u'example.com')
        acc.realname = u'User Name'
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
        acc.address = account.Address(u'user', u'example.com')
        acc.realname = u'User Name'
        with mock.patch('alot.db.message.settings.get_accounts',
                        mock.Mock(return_value=[acc])):
            msg = message.Message(mock.Mock(), MockNotmuchMessage())
        self.assertEqual(msg.get_author(), ('Unknown', ''))
