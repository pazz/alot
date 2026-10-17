# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

from alot.buffers import EnvelopeBuffer
from alot.db.envelope import Envelope


class TestEnvelopeBuffer(unittest.TestCase):

    @mock.patch('alot.buffers.envelope.settings')
    def test_focus_last_and_first_scroll_the_body(self, settings):
        settings.get.return_value = []
        # a first line taller than the view must be shown from its top
        body = 'top' + 'x' * 97 + '\n' + '\n'.join(
            'line%d' % i for i in range(50))
        buf = EnvelopeBuffer(mock.Mock(), Envelope(bodytext=body))

        def visible():
            return [r.decode().strip() for r in buf.render((20, 3)).text]

        buf.focus_last()
        self.assertEqual(visible(), ['line47', 'line48', 'line49'])
        buf.focus_first()
        self.assertEqual(visible()[0], 'topxxxxxxxxxxxxxxxxx')
