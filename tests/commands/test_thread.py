# encoding=utf-8
# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Test suite for alot.commands.thread module."""
import email
import email.mime.text
import os
import tempfile
import unittest
from unittest import mock

from alot.commands import thread
from alot.account import Account
from alot.db.attachment import Attachment

from .. import utilities

# Good descriptive test names often don't fit PEP8, which is meant to cover
# functions meant to be called by humans.
# pylint: disable=invalid-name

# These are tests, don't worry about names like "foo" and "bar"
# pylint: disable=blacklisted-name


class _AccountTestClass(Account):
    """Implements stubs for ABC methods."""

    def send_mail(self, mail):
        pass


class TestDetermineSender(unittest.TestCase):

    header_priority = ["From", "To", "Cc", "Envelope-To", "X-Envelope-To",
                       "Delivered-To"]
    mailstring = '\n'.join([
        "From: from@example.com",
        "To: to@example.com",
        "Cc: cc@example.com",
        "Envelope-To: envelope-to@example.com",
        "X-Envelope-To: x-envelope-to@example.com",
        "Delivered-To: delivered-to@example.com",
        "Subject: Alot test",
        "\n",
        "Some content",
        ])
    mail = email.message_from_string(mailstring)

    def _test(self, accounts=(), expected=(), mail=None, header_priority=None,
              force_realname=False, force_address=False):
        """This method collects most of the steps that need to be done for most
        tests.  Especially a closure to mock settings.get and a mock for
        settings.get_accounts are set up."""
        mail = self.mail if mail is None else mail
        header_priority = self.header_priority if header_priority is None \
            else header_priority

        def settings_get(arg):
            """Mock function for setting.get()"""
            if arg == "reply_account_header_priority":
                return header_priority
            elif arg.endswith('_force_realname'):
                return force_realname
            elif arg.endswith('_force_address'):
                return force_address

        with mock.patch('alot.commands.thread.settings.get_accounts',
                        mock.Mock(return_value=accounts)):
            with mock.patch('alot.commands.thread.settings.get', settings_get):
                actual = thread.determine_sender(mail)
        self.assertTupleEqual(actual, expected)

    def test_assert_that_some_accounts_are_defined(self):
        with mock.patch('alot.commands.thread.settings.get_accounts',
                        mock.Mock(return_value=[])) as cm1:
            with self.assertRaises(AssertionError) as cm2:
                thread.determine_sender(None)
        expected = ('no accounts set!',)
        cm1.assert_called_once_with()
        self.assertTupleEqual(cm2.exception.args, expected)

    def test_default_account_is_used_if_no_match_is_found(self):
        account1 = _AccountTestClass(address='foo@example.com')
        account2 = _AccountTestClass(address='bar@example.com')
        expected = ('foo@example.com', account1)
        self._test(accounts=[account1, account2], expected=expected)

    def test_matching_address_and_account_are_returned(self):
        account1 = _AccountTestClass(address='foo@example.com')
        account2 = _AccountTestClass(address='to@example.com')
        account3 = _AccountTestClass(address='bar@example.com')
        expected = ('to@example.com', account2)
        self._test(accounts=[account1, account2, account3], expected=expected)

    def test_force_realname_has_real_name_in_returned_address_if_defined(self):
        account1 = _AccountTestClass(address='foo@example.com')
        account2 = _AccountTestClass(address='to@example.com', realname='Bar')
        account3 = _AccountTestClass(address='baz@example.com')
        expected = ('Bar <to@example.com>', account2)
        self._test(accounts=[account1, account2, account3], expected=expected,
                   force_realname=True)

    def test_doesnt_fail_with_force_realname_if_real_name_not_defined(self):
        account1 = _AccountTestClass(address='foo@example.com')
        account2 = _AccountTestClass(address='to@example.com')
        account3 = _AccountTestClass(address='bar@example.com')
        expected = ('to@example.com', account2)
        self._test(accounts=[account1, account2, account3], expected=expected,
                   force_realname=True)

    def test_with_force_address_main_address_is_always_used(self):
        # In python 3.4 this and the next test could be written as subtests.
        account1 = _AccountTestClass(address='foo@example.com')
        account2 = _AccountTestClass(address='bar@example.com',
                                     aliases=['to@example.com'])
        account3 = _AccountTestClass(address='bar@example.com')
        expected = ('bar@example.com', account2)
        self._test(accounts=[account1, account2, account3], expected=expected,
                   force_address=True)

    def test_without_force_address_matching_address_is_used(self):
        # In python 3.4 this and the previous test could be written as
        # subtests.
        account1 = _AccountTestClass(address='foo@example.com')
        account2 = _AccountTestClass(address='bar@example.com',
                                     aliases=['to@example.com'])
        account3 = _AccountTestClass(address='baz@example.com')
        expected = ('to@example.com', account2)
        self._test(accounts=[account1, account2, account3], expected=expected,
                   force_address=False)

    def test_uses_to_header_if_present(self):
        account1 = _AccountTestClass(address='foo@example.com')
        account2 = _AccountTestClass(address='to@example.com')
        account3 = _AccountTestClass(address='bar@example.com')
        expected = ('to@example.com', account2)
        self._test(accounts=[account1, account2, account3], expected=expected)

    def test_header_order_is_more_important_than_accounts_order(self):
        account1 = _AccountTestClass(address='cc@example.com')
        account2 = _AccountTestClass(address='to@example.com')
        account3 = _AccountTestClass(address='bcc@example.com')
        expected = ('to@example.com', account2)
        self._test(accounts=[account1, account2, account3], expected=expected)

    def test_accounts_can_be_found_by_alias_regex_setting(self):
        account1 = _AccountTestClass(address='foo@example.com')
        account2 = _AccountTestClass(address='to@example.com',
                                     alias_regexp=r'to\+.*@example.com')
        account3 = _AccountTestClass(address='bar@example.com')
        mailstring = self.mailstring.replace('to@example.com',
                                             'to+some_tag@example.com')
        mail = email.message_from_string(mailstring)
        expected = ('to+some_tag@example.com', account2)
        self._test(accounts=[account1, account2, account3], expected=expected,
                   mail=mail)


class TestForwardCommand(unittest.TestCase):

    @mock.patch('alot.commands.thread.settings.get', return_value='Fw: ')
    @mock.patch('alot.commands.thread.determine_sender',
                return_value=('me', None))
    @utilities.async_test
    async def test_subject_prefix(self, *_):
        for subject, expected in [('Hi', 'Fw: Hi'), ('FWD: Hi', 'FWD: Hi')]:
            with self.subTest(subject=subject):
                msg = mock.Mock()
                msg.get_email.return_value = email.message_from_string(
                    'Subject: %s\n\n' % subject)
                ui = utilities.make_ui(apply_command=mock.AsyncMock())
                await thread.ForwardCommand(msg, attach=True).apply(ui)
                envelope = ui.apply_command.await_args.args[0].envelope
                self.assertEqual(envelope.get('Subject'), expected)


class TestReplyCommand(unittest.TestCase):

    @mock.patch('alot.commands.thread.settings.get_hook',
                mock.Mock(return_value=None))
    @mock.patch('alot.commands.thread.settings.get',
                mock.Mock(side_effect={'reply_subject_prefix': 'Re: '}.get))
    @mock.patch('alot.commands.thread.determine_sender',
                mock.Mock(return_value=('me@example.com', mock.Mock())))
    @utilities.async_test
    async def test_list_reply_uses_list_post(self):
        msg = mock.Mock()
        msg.get_body_text.return_value = ''
        msg.get_email.return_value = email.message_from_string(
            'From: a@example.com\nTo: list@example.org\n'
            'List-Post: <mailto:post@example.org?subject=x>\n\n')
        ui = utilities.make_ui(apply_command=mock.AsyncMock())
        await thread.ReplyCommand(msg, listreply=True).apply(ui)
        envelope = ui.apply_command.await_args.args[0].envelope
        self.assertEqual(envelope.get('To'), 'post@example.org')


class TestOpenAttachmentCommand(unittest.TestCase):

    @mock.patch('alot.commands.thread.settings.mailcap_find_match',
                return_value=(None, {'view': 'cat %{charset}'}))
    @utilities.async_test
    async def test_unsafe_parameter(self, _):
        part = email.message.Message()
        part['Content-Type'] = 'text/plain; charset="a;b"'
        attachment = mock.Mock(**{
            'get_content_type.return_value': 'text/plain',
            'get_mime_representation.return_value': part})
        ui = utilities.make_ui(apply_command=mock.AsyncMock())
        await thread.OpenAttachmentCommand(attachment).apply(ui)
        ui.apply_command.assert_not_awaited()
        ui.notify.assert_called_once()


class TestSaveAttachmentCommand(unittest.TestCase):

    @utilities.async_test
    async def test_asks_before_overwriting(self):
        part = email.mime.text.MIMEText('new')
        part.add_header('Content-Disposition', 'attachment', filename='a.txt')
        attachment = Attachment(part)
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, 'a.txt')
            for answer, content in (('no', 'old'), ('yes', 'new')):
                with open(target, 'w') as f:
                    f.write('old')
                ui = utilities.make_ui(choice=mock.AsyncMock(
                    return_value=answer))
                ui.current_buffer.get_selected_message.return_value.\
                    get_attachments.return_value = [attachment]
                await thread.SaveAttachmentCommand(all=True, path=d).apply(ui)
                ui.choice.assert_awaited_once()
                with open(target) as f:
                    self.assertEqual(f.read(), content)


class TestPipeCommand(unittest.TestCase):

    @utilities.async_test
    async def test_foreground_notifies_stdout_and_leaves_stderr(self):
        ui = utilities.make_ui()
        ui.current_buffer.get_selected_message.return_value.\
            get_message_id.return_value = 'id'
        cmd = thread.PipeCommand(['echo out; echo warning >&2'],
                                 notify_stdout=True, format='id')
        await cmd.apply(ui)
        ui.notify.assert_called_once_with('out\n')

    @utilities.async_test
    async def test_pipes_mime_parts(self):
        mail = email.message.EmailMessage()
        mail.set_content('plain\ttext\n')
        mail.add_alternative('<p>html</p>\n', subtype='html')
        plain, html = mail.get_payload()
        cases = [('plain', None, 'plain\ttext\n'),
                 ('html', None, '<p>html</p>\n'),
                 ('mimepart', None, '<p>html</p>\n'),
                 ('mimepart', Attachment(plain), 'plain\ttext\n')]
        for fmt, focus, expected in cases:
            ui = utilities.make_ui()
            ui.get_deep_focus.return_value.mimepart = focus
            msg = ui.current_buffer.get_selected_message.return_value
            msg.get_email.return_value = mail
            msg.get_mime_part.return_value = html
            cmd = thread.PipeCommand(['cat'], notify_stdout=True, format=fmt)
            await cmd.apply(ui)
            ui.notify.assert_called_once_with(expected)

    @utilities.async_test
    async def test_pipes_binary_mimepart_unchanged(self):
        data = bytes(range(256))
        part = email.message.EmailMessage()
        part.set_content(data, maintype='application', subtype='octet-stream')
        with tempfile.NamedTemporaryFile() as out:
            ui = utilities.make_ui()
            ui.get_deep_focus.return_value.mimepart = part
            msg = ui.current_buffer.get_selected_message.return_value
            msg.get_email.return_value = part
            cmd = thread.PipeCommand(['cat > ' + out.name], format='mimepart')
            await cmd.apply(ui)
            self.assertEqual(out.read(), data)


class TestQuoteText(unittest.TestCase):

    @mock.patch('alot.commands.thread.settings.get_hook',
                mock.Mock(return_value=None))
    @mock.patch('alot.commands.thread.settings.get',
                mock.Mock(return_value='> '))
    def test_quote_prefix(self):
        self.assertEqual(thread.quote_text('a\nb'), '> a\n> b\n')

    @mock.patch('alot.commands.thread.settings.get_hook',
                mock.Mock(return_value=None))
    @mock.patch('alot.commands.thread.settings.get',
                mock.Mock(return_value='> '))
    def test_strips_csi(self):
        self.assertEqual(thread.quote_text('\x1b[1ma\x1b[0m'), '> a\n')

    @mock.patch('alot.commands.thread.settings.get_hook',
                mock.Mock(return_value=str.upper))
    def test_text_quote_hook(self):
        self.assertEqual(thread.quote_text('a\nb'), 'A\nB')
