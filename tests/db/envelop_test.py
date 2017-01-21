# encoding=utf-8
from __future__ import absolute_import

import unittest

from alot.db import envelope


class TestEnvelopeMethods(unittest.TestCase):

    def test_setitem_stores_text_unchanged(self):
        "Just ensure that the value is set and unchanged"
        e = envelope.Envelope()
        e['Subject'] = u'sm\xf8rebr\xf8d'
        self.assertEqual(e['Subject'], u'sm\xf8rebr\xf8d')
