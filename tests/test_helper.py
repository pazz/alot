# encoding=utf-8
# Copyright © 2016-2018 Dylan Baker
# Copyright © 2017 Lucas Hoffman

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Test suite for alot.helper module."""

import datetime
import errno
import os
import random
import unittest
from unittest import mock

from alot import helper

from . import utilities

# Descriptive names for tests often violate PEP8. That's not an issue, users
# aren't meant to call these functions.
# pylint: disable=invalid-name

# They're tests, only add docstrings when it makes sense
# pylint: disable=missing-docstring


class TestHelperShortenAuthorString(unittest.TestCase):

    authors = u'King Kong, Mucho Muchacho, Jaime Huerta, Flash Gordon'

    def test_high_maxlength_keeps_string_intact(self):
        short = helper.shorten_author_string(self.authors, 60)
        self.assertEqual(short, self.authors)

    def test_shows_only_first_names_if_they_fit(self):
        short = helper.shorten_author_string(self.authors, 40)
        self.assertEqual(short, u"King, Mucho, Jaime, Flash")

    def test_adds_ellipses_to_long_first_names(self):
        short = helper.shorten_author_string(self.authors, 20)
        self.assertEqual(short, u"King, …, Jai…, Flash")

    def test_replace_all_but_first_name_with_ellipses(self):
        short = helper.shorten_author_string(self.authors, 10)
        self.assertEqual(short, u"King, …")

    def test_shorten_first_name_with_ellipses(self):
        short = helper.shorten_author_string(self.authors, 2)
        self.assertEqual(short, u"K…")

    def test_only_display_initial_letter_for_maxlength_1(self):
        short = helper.shorten_author_string(self.authors, 1)
        self.assertEqual(short, u"K")


class TestShellQuote(unittest.TestCase):

    def test_all_strings_are_sourrounded_by_single_quotes(self):
        quoted = helper.shell_quote("hello")
        self.assertEqual(quoted, "'hello'")

    def test_single_quotes_are_escaped_using_double_quotes(self):
        quoted = helper.shell_quote("hello'there")
        self.assertEqual(quoted, """'hello'"'"'there'""")


class TestHumanizeSize(unittest.TestCase):

    def test_small_numbers_are_converted_to_strings_directly(self):
        readable = helper.humanize_size(1)
        self.assertEqual(readable, "1")
        readable = helper.humanize_size(123)
        self.assertEqual(readable, "123")

    def test_numbers_above_1024_are_converted_to_kilobyte(self):
        readable = helper.humanize_size(1023)
        self.assertEqual(readable, "1023")
        readable = helper.humanize_size(1024)
        self.assertEqual(readable, "1KiB")
        readable = helper.humanize_size(1234)
        self.assertEqual(readable, "1KiB")

    def test_numbers_above_1048576_are_converted_to_megabyte(self):
        readable = helper.humanize_size(1024*1024-1)
        self.assertEqual(readable, "1023KiB")
        readable = helper.humanize_size(1024*1024)
        self.assertEqual(readable, "1.0MiB")

    def test_megabyte_numbers_are_converted_with_precision_1(self):
        readable = helper.humanize_size(1234*1024)
        self.assertEqual(readable, "1.2MiB")

    def test_numbers_are_not_converted_to_gigabyte(self):
        readable = helper.humanize_size(1234*1024*1024)
        self.assertEqual(readable, "1234.0MiB")


class TestSplitCommandline(unittest.TestCase):

    def _test(self, base, expected):
        """Shared helper to reduce some boilerplate."""
        actual = helper.split_commandline(base)
        self.assertListEqual(actual, expected)

    def test_simple(self):
        base = 'echo "foo";sleep 1'
        expected = ['echo "foo"', 'sleep 1']
        self._test(base, expected)

    def test_single(self):
        base = 'echo "foo bar"'
        expected = [base]
        self._test(base, expected)

    def test_unicode(self):
        base = u'echo "foo";sleep 1'
        expected = ['echo "foo"', 'sleep 1']
        self._test(base, expected)


class TestSplitCommandstring(unittest.TestCase):

    def _test(self, base, expected):
        """Shared helper to reduce some boilerplate."""
        actual = helper.split_commandstring(base)
        self.assertListEqual(actual, expected)

    def test_bytes(self):
        base = 'echo "foo bar"'
        expected = ['echo', 'foo bar']
        self._test(base, expected)

    def test_unicode(self):
        base = 'echo "foo €"'
        expected = ['echo', 'foo €']
        self._test(base, expected)


class TestStringSanitize(unittest.TestCase):

    def test_tabs(self):
        base = 'foo\tbar\noink\n'
        expected = 'foo' + ' ' * 5 + 'bar\noink\n'
        actual = helper.string_sanitize(base)
        self.assertEqual(actual, expected)


class TestStringDecode(unittest.TestCase):

    def _test(self, base, expected, encoding='ascii'):
        actual = helper.string_decode(base, encoding)
        self.assertEqual(actual, expected)

    def test_ascii_bytes(self):
        base = u'test'.encode('ascii')
        expected = u'test'
        self._test(base, expected)

    def test_utf8_bytes(self):
        base = u'test'.encode('utf-8')
        expected = u'test'
        self._test(base, expected, 'utf-8')

    def test_unicode(self):
        base = u'test'
        expected = u'test'
        self._test(base, expected)


class TestPrettyDatetime(unittest.TestCase):

    # TODO: Currently these tests use the ampm format based on whether or not
    # the testing machine's locale sets them. To be really good mock should be
    # used to change the locale between an am/pm locale and a 24 hour locale
    # and test both scenarios.

    __patchers = []

    @classmethod
    def setUpClass(cls):
        # Create a random number generator, but seed it so that it will produce
        # deterministic output. This is used to select a subset of possible
        # values for each of the tests in this class, since otherwise they
        # would get really expensive (time wise).
        cls.random = random.Random()
        cls.random.seed(42)

        # Pick an exact date to ensure that the tests run the same no matter
        # what time of day they're run.
        cls.now = datetime.datetime(2000, 1, 5, 12, 0, 0, 0)

        # Mock datetime.now, which ensures that the time is always the same
        # removing race conditions from the tests.
        dt = mock.Mock()
        dt.now = mock.Mock(return_value=cls.now)
        cls.__patchers.append(mock.patch('alot.helper.datetime', dt))

        for p in cls.__patchers:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls.__patchers:
            p.stop()

    def test_just_now(self):
        for i in (self.random.randint(0, 60) for _ in range(5)):
            test = self.now - datetime.timedelta(seconds=i)
            actual = helper.pretty_datetime(test)
            self.assertEqual(actual, u'just now')

    def test_x_minutes_ago(self):
        for i in (self.random.randint(60, 3600) for _ in range(10)):
            test = self.now - datetime.timedelta(seconds=i)
            actual = helper.pretty_datetime(test)
            self.assertEqual(
                actual, u'{}min ago'.format((self.now - test).seconds // 60))

    def test_x_hours_ago(self):
        for i in (self.random.randint(3600, 3600 * 6) for _ in range(10)):
            test = self.now - datetime.timedelta(seconds=i)
            actual = helper.pretty_datetime(test)
            self.assertEqual(
                actual, u'{}h ago'.format((self.now - test).seconds // 3600))

    # TODO: yesterday
    # TODO: yesterday > now > a year
    # TODO: last year
    # XXX: when can the last else be hit?

    @staticmethod
    def _future_expected(test):
        if test.strftime('%p'):
            expected = test.strftime('%I:%M%p').lower()
        else:
            expected = test.strftime('%H:%M')
        expected = expected
        return expected

    def test_future_seconds(self):
        test = self.now + datetime.timedelta(seconds=30)
        actual = helper.pretty_datetime(test)
        expected = self._future_expected(test)
        self.assertEqual(actual, expected)

    # Returns 'just now', instead of 'from future' or something similar
    @unittest.expectedFailure
    def test_future_minutes(self):
        test = self.now + datetime.timedelta(minutes=5)
        actual = helper.pretty_datetime(test)
        expected = test.strftime('%a ') + self._future_expected(test)
        self.assertEqual(actual, expected)

    # Returns 'just now', instead of 'from future' or something similar
    @unittest.expectedFailure
    def test_future_hours(self):
        test = self.now + datetime.timedelta(hours=1)
        actual = helper.pretty_datetime(test)
        expected = test.strftime('%a ') + self._future_expected(test)
        self.assertEqual(actual, expected)

    # Returns 'just now', instead of 'from future' or something similar
    @unittest.expectedFailure
    def test_future_days(self):
        def make_expected():
            # Uses the hourfmt instead of the hourminfmt from pretty_datetime
            if test.strftime('%p'):
                expected = test.strftime('%I%p')
            else:
                expected = test.strftime('%Hh')
            expected = expected.decode('utf-8')
            return expected

        test = self.now + datetime.timedelta(days=1)
        actual = helper.pretty_datetime(test)
        expected = test.strftime('%a ') + make_expected()
        self.assertEqual(actual, expected)

    # Returns 'just now', instead of 'from future' or something similar
    @unittest.expectedFailure
    def test_future_week(self):
        test = self.now + datetime.timedelta(days=7)
        actual = helper.pretty_datetime(test)
        expected = test.strftime('%b %d')
        self.assertEqual(actual, expected)

    # Returns 'just now', instead of 'from future' or something similar
    @unittest.expectedFailure
    def test_future_month(self):
        test = self.now + datetime.timedelta(days=31)
        actual = helper.pretty_datetime(test)
        expected = test.strftime('%b %d')
        self.assertEqual(actual, expected)

    # Returns 'just now', instead of 'from future' or something similar
    @unittest.expectedFailure
    def test_future_year(self):
        test = self.now + datetime.timedelta(days=365)
        actual = helper.pretty_datetime(test)
        expected = test.strftime('%b %Y')
        self.assertEqual(actual, expected)


class TestCallCmd(unittest.TestCase):
    """Tests for the call_cmd function."""

    def test_no_stdin(self):
        out, err, code = helper.call_cmd(['echo', '-n', 'foo'])
        self.assertEqual(out, u'foo')
        self.assertEqual(err, u'')
        self.assertEqual(code, 0)

    def test_no_stdin_unicode(self):
        out, err, code = helper.call_cmd(['echo', '-n', '�'])
        self.assertEqual(out, u'�')
        self.assertEqual(err, u'')
        self.assertEqual(code, 0)

    def test_stdin(self):
        out, err, code = helper.call_cmd(['cat'], stdin='�')
        self.assertEqual(out, u'�')
        self.assertEqual(err, u'')
        self.assertEqual(code, 0)

    def test_no_such_command(self):
        out, err, code = helper.call_cmd(['thiscommandabsolutelydoesntexist'])
        self.assertEqual(out, u'')

        # We don't control the output of err, the shell does. Therefore simply
        # assert that the shell said *something*
        self.assertNotEqual(err, u'')
        self.assertEqual(code, errno.ENOENT)

    def test_no_such_command_stdin(self):
        out, err, code = helper.call_cmd(['thiscommandabsolutelydoesntexist'],
                                         stdin='foo')
        self.assertEqual(out, u'')

        # We don't control the output of err, the shell does. Therefore simply
        # assert that the shell said *something*
        self.assertNotEqual(err, u'')
        self.assertEqual(code, errno.ENOENT)

    def test_bad_argument_stdin(self):
        out, err, code = helper.call_cmd(['cat', '-Y'], stdin='�')
        self.assertEqual(out, u'')
        self.assertNotEqual(err, u'')

        # We don't control this, although 1 might be a fairly safe guess, we
        # know for certain it should *not* return 0
        self.assertNotEqual(code, 0)

    def test_bad_argument(self):
        out, err, code = helper.call_cmd(['cat', '-Y'])
        self.assertEqual(out, u'')
        self.assertNotEqual(err, u'')

        # We don't control this, although 1 might be a fairly safe guess, we
        # know for certain it should *not* return 0
        self.assertNotEqual(code, 0)

    def test_os_errors_from_popen_are_caught(self):
        with mock.patch('subprocess.Popen',
                        mock.Mock(side_effect=OSError(42, u'foobar'))):
            out, err, code = helper.call_cmd(
                ['does_not_matter_as_subprocess_popen_is_mocked'])
        self.assertEqual(out, u'')
        self.assertEqual(err, u'foobar')
        self.assertEqual(code, 42)


class TestShorten(unittest.TestCase):

    def test_lt_maxlen(self):
        expected = u'a string'
        actual = helper.shorten(expected, 25)
        self.assertEqual(expected, actual)

    def test_eq_maxlen(self):
        expected = 'a string'
        actual = helper.shorten(expected, len(expected))
        self.assertEqual(expected, actual)

    def test_gt_maxlen(self):
        expected = u'a long string…'
        actual = helper.shorten('a long string that is full of text', 14)
        self.assertEqual(expected, actual)


class TestCallCmdAsync(unittest.TestCase):

    @utilities.async_test
    async def test_no_stdin(self):
        ret = await helper.call_cmd_async(['echo', '-n', 'foo'])
        self.assertEqual(ret[0], 'foo')

    @utilities.async_test
    async def test_stdin(self):
        ret = await helper.call_cmd_async(['cat', '-'], stdin='foo')
        self.assertEqual(ret[0], 'foo')

    @utilities.async_test
    async def test_env_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            ret = await helper.call_cmd_async(
                ['python3', '-c', 'import os; '
                                  'print(os.environ.get("foo", "fail"), end="")'
                ],
                env={'foo': 'bar'})
        self.assertEqual(ret[0], 'bar')

    @utilities.async_test
    async def test_env_doesnt_pollute(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            await helper.call_cmd_async(['echo', '-n', 'foo'],
                                        env={'foo': 'bar'})
            self.assertEqual(os.environ, {})

    @utilities.async_test
    async def test_command_fails(self):
        _, err, ret = await helper.call_cmd_async(['_____better_not_exist'])
        self.assertEqual(ret, 1)
        self.assertTrue(err)


class TestGetEnv(unittest.TestCase):
    env_name = 'XDG_CONFIG_HOME'
    default = '~/.config'

    def test_env_not_set(self):
        with mock.patch.dict('os.environ'):
            if self.env_name in os.environ:
                del os.environ[self.env_name]
            self.assertEqual(helper.get_xdg_env(self.env_name, self.default),
                             self.default)

    def test_env_empty(self):
        with mock.patch.dict('os.environ', {self.env_name: ''}):
            self.assertEqual(helper.get_xdg_env(self.env_name, self.default),
                             self.default)

    def test_env_not_empty(self):
        custom_path = '/my/personal/config/home'

        with mock.patch.dict('os.environ', {self.env_name: custom_path}):
            self.assertEqual(helper.get_xdg_env(self.env_name, self.default),
                             custom_path)


class TestParseMailto(unittest.TestCase):

    def test_parsing_working(self):
        uri = 'mailto:test%40example.org?Subject=Re%3A%20Hello\
&In-Reply-To=%3CC8CE9EFD-CB23-4BC0-B70D-9B7FEAD59F8C%40example.org%3E'
        actual = helper.parse_mailto(uri)
        expected = ({'To': ['test@example.org'],
                     'Subject': ['Re: Hello'],
                     'In-reply-to': ['<C8CE9EFD-CB23-4BC0-B70D-9B7FEAD59F8C@example.org>']}, '')
        self.assertEqual(actual, expected)
