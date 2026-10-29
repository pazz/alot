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


class TestTrimSubject(unittest.TestCase):

    def test_table(self):
        patch = '[PATCH 01/11] ipa: document the class'
        cases = [
            (patch, 'Re: [libcamera-devel] ' + patch, 'Re: [libcamera-devel] ...'),
            ('Re: foo', 'RE: Re: foo', 'RE: ...'),
            ('foo', 'foo', '...'),
            ('foo', 'foobar', 'foobar'),
            ('foo', 'barfoo', 'barfoo'),
            ('Your subject', 'Re: Your subject IMPORTANT CORRECTION',
             'Re: Your subject IMPORTANT CORRECTION'),
            ('', 'Re: foo', 'Re: foo'),
            ('AW: Termin', 'Re: Termin', 'Re: ...'),
            ('SV: Re: Termin', 'Re: Termin', 'Re: ...'),
            ('AW: Hi', 'Re: Say Hi', 'Re: Say Hi'),
            ('AW: Termin', '回复：Termin', '回复：...'),
            ('Termin', 'Re:Termin', 'Re:...'),
            ('Termin', '回复：Termin', '回复：...'),
            ('Re: foo', 'Re: barfoo', 'Re: barfoo'),
            (None, 'foo', 'foo'),
        ]
        for parent, child, shown in cases:
            with self.subTest(parent=parent, child=child):
                self.assertEqual(thread.trim_subject(child, parent), shown)


class TestMessageSummaryWidget(unittest.TestCase):

    def summary(self, mode, subject, parent_subject='foo'):
        parent = mock.Mock(**{'get_subject.return_value': parent_subject})
        msg = mock.Mock(**{'get_author.return_value': ('Ada', 'ada@x'),
                           'get_datestring.return_value': 'Sep 21',
                           'get_subject.return_value': subject})
        widget = thread.MessageSummaryWidget.__new__(
            thread.MessageSummaryWidget)
        widget.message = msg
        widget.parent = parent
        with mock.patch('alot.widgets.thread.settings.get',
                        return_value=mode):
            return str(widget)

    def test_modes(self):
        self.assertEqual(self.summary('none', 'Re: foo'), 'Ada (Sep 21)')
        self.assertEqual(self.summary('all', 'Re: foo'),
                         'Ada (Sep 21): Re: foo')
        self.assertEqual(self.summary('trimmed', 'Re: foo'),
                         'Ada (Sep 21): Re: ...')

    def test_no_separator_without_subject(self):
        self.assertEqual(self.summary('all', ''), 'Ada (Sep 21)')


class TestThreadTreeSubjects(unittest.TestCase):

    @staticmethod
    def message(mid, subject):
        return mock.Mock(**{'get_message_id.return_value': mid,
                            'get_subject.return_value': subject,
                            'get_author.return_value': ('Ada', 'ada@x'),
                            'get_datestring.return_value': 'Sep 21',
                            'get_tags.return_value': []})

    def test_reply_is_trimmed_against_its_parent(self):
        parent = self.message('p', '[PATCH 1/2] fix it')
        reply = self.message('r', 'Re: [PATCH 1/2] fix it')
        replies = {'p': [reply], 'r': []}
        thr = mock.Mock(**{
            'get_toplevel_messages.return_value': [parent],
            'get_replies_to.side_effect':
                lambda m: replies[m.get_message_id()]})
        config = {'thread_message_subjects': 'trimmed',
                  'msg_summary_hides_threadwide_tags': False}
        with mock.patch('alot.widgets.thread.settings') as settings:
            settings.get.side_effect = config.get
            settings.get_theming_attribute.return_value = None
            tree = thread.ThreadTree(thr)
            summary = tree['r']._get_summary()
            text = str(summary)
        self.assertEqual(text, 'Ada (Sep 21): Re: ...')
        self.assertEqual(summary.rows((12,)), 1)  # clipped, not wrapped
