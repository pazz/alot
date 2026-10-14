# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest

from alot.db.attachment import Attachment
from alot.db.utils import decrypted_message_from_bytes


class TestAttachment(unittest.TestCase):

    def test_mime_representation_keeps_disposition(self):
        # the filename decodes to a string containing CR/LF (issue #1431)
        part = decrypted_message_from_bytes(
            b'Content-Type: application/pdf\n'
            b'Content-Disposition: attachment;\n'
            b' filename="a =?utf-8?b?Yi5wZGYiOw0K?= size=1"\n'
            b'\n'
            b'data\n')
        mime = Attachment(part).get_mime_representation()
        self.assertEqual(mime['Content-Disposition'],
                         part['Content-Disposition'])
        self.assertIsNone(mime.get_param('maxlinelen',
                                         header='Content-Disposition'))
