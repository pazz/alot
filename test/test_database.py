import unittest
from corpus import Corpus
import os


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus()

    def test_messagefile(self):
        msg = self.corpus.get_notmuch_msg_by_id('TESTMAIL1@mail.com')
        msgfile = os.path.basename(msg.get_filename())
        self.assertEqual(msgfile, 'mail1.eml')

    def tearDown(self):
        del(self.corpus)

