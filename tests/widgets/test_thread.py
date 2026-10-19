# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

from alot.db.utils import decrypted_message_from_bytes
from alot.widgets import thread


class TestMessageTree(unittest.TestCase):

    @mock.patch('alot.widgets.thread.settings', mock.Mock())
    @mock.patch('alot.widgets.thread.TextlinesList')
    def test_source_is_file_content(self, textlines):
        path = 'tests/static/mail/utf8.eml'
        with open(path, 'rb') as f:
            raw = f.read()
        msg = mock.Mock(**{
            'get_filename.return_value': path,
            'get_email.return_value': decrypted_message_from_bytes(raw)})
        tree = thread.MessageTree.__new__(thread.MessageTree)
        tree._message = msg
        tree._sourcetree = None
        tree._get_source()
        self.assertEqual(textlines.call_args.args[0], raw.decode())

    @mock.patch('alot.widgets.thread.settings', mock.Mock())
    @mock.patch('alot.widgets.thread.ANSIText')
    def test_mimepart_without_headers_is_a_leaf(self, ansitext):
        part = decrypted_message_from_bytes(b'\n\nimplicit text/plain\n')
        self.assertFalse(part)  # no headers, so length 0
        tree = thread.MessageTree.__new__(thread.MessageTree)
        _, subtrees = tree._text_tree_to_widget_tree(('text/plain', part))
        self.assertIsNone(subtrees)
        self.assertIs(ansitext.call_args.kwargs['mimepart'], part)
