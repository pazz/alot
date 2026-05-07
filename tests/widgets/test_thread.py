# Copyright © 2026 alot contributors
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import unittest
from unittest import mock

import urwid


def _make_summary_widget(subject_mode='never', msg_subject='',
                         thread_subject='', parent_subject=None,
                         msg_tags=None, thread_intersection_tags=None):
    """Construct a MessageSummaryWidget with mocked settings & message.

    ``parent_subject=None`` means the message is at the root of the thread
    tree (no parent). Otherwise a mock parent message is built and passed
    to the widget so 'different' mode can compare against it.
    """
    msg = mock.Mock()
    msg.get_author.return_value = ('Alice', 'alice@example.com')
    msg.get_datestring.return_value = '2026-01-01'
    msg.get_subject.return_value = msg_subject
    msg.get_tags.return_value = msg_tags or []
    msg.get_thread.return_value.get_tags.return_value = (
        thread_intersection_tags or set())
    msg.get_thread.return_value.get_subject.return_value = thread_subject

    parent = None
    if parent_subject is not None:
        parent = mock.Mock()
        parent.get_subject.return_value = parent_subject

    settings_get = {
        'msg_summary_hides_threadwide_tags': True,
        'msg_summary_show_subject': subject_mode,
    }

    attr = ('default', '', 'default', 'default', 'default', 'default')

    def fake_tag_repr(tag, *args, **kwargs):
        return {'translated': tag, 'normal': attr, 'focussed': attr}

    with mock.patch('alot.widgets.thread.settings') as s, \
            mock.patch('alot.widgets.globals.settings') as g:
        s.get.side_effect = lambda k: settings_get[k]
        s.get_theming_attribute.return_value = attr
        g.get_tagstring_representation.side_effect = fake_tag_repr
        from alot.widgets.thread import MessageSummaryWidget
        return MessageSummaryWidget(msg, parent_message=parent)


def _column_widgets(widget):
    """Return the bare widgets inside the urwid.Columns of a summary."""
    columns = widget._w.original_widget
    return [w for w, _ in columns.contents]


def _column_texts(widget):
    """Return only the urwid.Text widgets' contents inside a summary."""
    return [w.text for w in _column_widgets(widget)
            if isinstance(w, urwid.Text)]


class TestMessageSummaryWidget(unittest.TestCase):

    def test_never_mode_does_not_add_subject_column(self):
        """In 'never' mode (the default) the summary line keeps its existing
        single text column (auteur (date)) — backward compatibility."""
        widget = _make_summary_widget(
            subject_mode='never', msg_subject='Hello world')
        texts = _column_texts(widget)
        self.assertEqual(texts, ['Alice (2026-01-01)'])

    def test_always_mode_adds_subject_column(self):
        """In 'always' mode the message subject is rendered as a separate
        text column on the summary line."""
        widget = _make_summary_widget(
            subject_mode='always', msg_subject='Hello world')
        texts = _column_texts(widget)
        self.assertIn('Hello world', texts)

    def test_different_mode_root_always_shows(self):
        """In 'different' mode, a root message (no parent) always shows
        its subject so the user has thread context when the thread is
        folded — even when the subject equals the thread subject."""
        widget = _make_summary_widget(
            subject_mode='different',
            msg_subject='Hello',
            thread_subject='Hello',
            parent_subject=None)
        texts = _column_texts(widget)
        self.assertIn('Hello', texts)

    def test_different_mode_hides_when_same_as_parent(self):
        """In 'different' mode, a reply whose subject normalises to the
        same value as its parent's subject is hidden."""
        widget = _make_summary_widget(
            subject_mode='different',
            msg_subject='Re: Hello',
            parent_subject='Hello')
        texts = _column_texts(widget)
        self.assertNotIn('Re: Hello', texts)
        self.assertEqual(texts, ['Alice (2026-01-01)'])

    def test_different_mode_shows_when_diverges_from_parent(self):
        """In 'different' mode, a reply whose normalised subject differs
        from its parent's normalised subject is shown."""
        widget = _make_summary_widget(
            subject_mode='different',
            msg_subject='Re: Goodbye',
            parent_subject='Hello')
        texts = _column_texts(widget)
        self.assertIn('Re: Goodbye', texts)

    def test_thread_tree_propagates_parent_to_replies(self):
        """ThreadTree must pass each message as the parent of its replies'
        MessageTree, so that 'different' mode can compare a reply's
        subject to its actual parent's subject (issue #566 follow-up)."""
        def fake_msg(mid):
            m = mock.Mock()
            m.get_message_id.return_value = mid
            m.get_author.return_value = ('A', 'a@b')
            m.get_datestring.return_value = ''
            m.get_subject.return_value = ''
            m.get_tags.return_value = []
            m.get_thread.return_value.get_tags.return_value = set()
            m.get_thread.return_value.get_subject.return_value = ''
            return m
        root = fake_msg('root-id')
        reply = fake_msg('reply-id')

        fake_thread = mock.Mock()
        fake_thread.get_toplevel_messages.return_value = [root]
        fake_thread.get_replies_to.side_effect = (
            lambda m: [reply] if m is root else [])

        attr = ('default', '', 'default', 'default', 'default', 'default')
        settings_get = {
            'msg_summary_hides_threadwide_tags': True,
            'msg_summary_show_subject': 'never',
        }
        with mock.patch('alot.widgets.thread.settings') as s:
            s.get.side_effect = lambda k: settings_get[k]
            s.get_theming_attribute.return_value = attr
            from alot.widgets.thread import ThreadTree
            tree = ThreadTree(fake_thread)

        self.assertIsNone(tree['root-id']._parent_message)
        self.assertIs(tree['reply-id']._parent_message, root)

    def test_different_mode_handles_mailing_list_tags(self):
        """In 'different' mode, ``[list-name]`` tags must not cause replies
        to look spuriously different from their parent (regression for
        the bug where every reply on a list was shown)."""
        widget = _make_summary_widget(
            subject_mode='different',
            msg_subject='[list-name] Re: Hello',
            parent_subject='[list-name] Hello')
        texts = _column_texts(widget)
        self.assertNotIn('[list-name] Re: Hello', texts)

    def test_subject_attr_picks_subject_even_for_even_rows(self):
        """An even row's subject column must be styled with the
        'subject_even' theme attribute so its background matches the
        even row background. Mirrors the pattern used by even/odd line
        attrs elsewhere in the theme."""
        msg = mock.Mock()
        msg.get_author.return_value = ('Alice', 'a@b.c')
        msg.get_datestring.return_value = ''
        msg.get_subject.return_value = 'Hello'
        msg.get_tags.return_value = []
        msg.get_thread.return_value.get_tags.return_value = set()
        msg.get_thread.return_value.get_subject.return_value = ''

        attr = ('default', '', 'default', 'default', 'default', 'default')
        settings_get = {
            'msg_summary_hides_threadwide_tags': True,
            'msg_summary_show_subject': 'always',
        }
        with mock.patch('alot.widgets.thread.settings') as s:
            s.get.side_effect = lambda k: settings_get[k]
            s.get_theming_attribute.return_value = attr
            from alot.widgets.thread import MessageSummaryWidget
            MessageSummaryWidget(msg, even=True)
            keys = [c.args[2]
                    for c in s.get_theming_attribute.call_args_list
                    if c.args[:2] == ('thread', 'summary')]
        self.assertIn('subject_even', keys)
        self.assertNotIn('subject_odd', keys)

    def test_subject_attr_picks_subject_odd_for_odd_rows(self):
        """An odd row's subject column must use 'subject_odd'."""
        msg = mock.Mock()
        msg.get_author.return_value = ('Alice', 'a@b.c')
        msg.get_datestring.return_value = ''
        msg.get_subject.return_value = 'Hello'
        msg.get_tags.return_value = []
        msg.get_thread.return_value.get_tags.return_value = set()
        msg.get_thread.return_value.get_subject.return_value = ''

        attr = ('default', '', 'default', 'default', 'default', 'default')
        settings_get = {
            'msg_summary_hides_threadwide_tags': True,
            'msg_summary_show_subject': 'always',
        }
        with mock.patch('alot.widgets.thread.settings') as s:
            s.get.side_effect = lambda k: settings_get[k]
            s.get_theming_attribute.return_value = attr
            from alot.widgets.thread import MessageSummaryWidget
            MessageSummaryWidget(msg, even=False)
            keys = [c.args[2]
                    for c in s.get_theming_attribute.call_args_list
                    if c.args[:2] == ('thread', 'summary')]
        self.assertIn('subject_odd', keys)
        self.assertNotIn('subject_even', keys)

    def test_subject_column_precedes_tag_widgets(self):
        """The subject column must be inserted before any TagWidget so it is
        truncated last when the line is short."""
        from alot.widgets.globals import TagWidget
        widget = _make_summary_widget(
            subject_mode='always',
            msg_subject='Hello world',
            msg_tags=['inbox'])
        widgets = _column_widgets(widget)
        subject_indexes = [i for i, w in enumerate(widgets)
                           if isinstance(w, urwid.Text)
                           and 'Hello world' in w.text]
        tag_indexes = [i for i, w in enumerate(widgets)
                       if isinstance(w, TagWidget)]
        self.assertTrue(subject_indexes, 'subject column missing')
        self.assertTrue(tag_indexes, 'tag widget missing')
        self.assertLess(max(subject_indexes), min(tag_indexes))
