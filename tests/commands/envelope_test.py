# encoding=utf-8
# Copyright © 2017 Dylan Baker

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

"""Tests for the alot.commands.envelope module."""

from __future__ import absolute_import
import os
import contextlib
import shutil
import tempfile
import unittest

import mock

from alot.commands import envelope
from alot.db.envelope import Envelope

# When using an assert from a mock a TestCase method might not use self. That's
# okay.
# pylint: disable=no-self-use


@contextlib.contextmanager
def temporary_directory(suffix='', prefix='', dir=None):
    # pylint: disable=redefined-builtin
    """Python3 interface implementation.

    Python3 provides a class that can be used as a context manager, which
    creates a temporary directory and removes it when the context manager
    exits. This function emulates enough of the interface of
    TemporaryDirectory, for this module to use, and is designed as a drop in
    replacement that can be replaced after the python3 port.

    The only user visible difference is that this does not implement the
    cleanup method that TemporaryDirectory does.
    """
    directory = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
    yield directory
    shutil.rmtree(directory)


class TestAttachCommand(unittest.TestCase):
    """Tests for the AttachCommaned class."""

    def test_single_path(self):
        """A test for an existing single path."""
        ui = mock.Mock()

        with temporary_directory() as d:
            testfile = os.path.join(d, 'foo')
            with open(testfile, 'w') as f:
                f.write('foo')

            cmd = envelope.AttachCommand(path=testfile)
            cmd.apply(ui)
        ui.current_buffer.envelope.attach.assert_called_with(testfile)

    def test_user(self):
        """A test for an existing single path prefaced with ~/."""
        ui = mock.Mock()

        with temporary_directory() as d:
            # This mock replaces expanduser to replace "~/" with a path to the
            # temporary directory. This is easier and more reliable than
            # relying on changing an environment variable (like HOME), since it
            # doesn't rely on CPython implementation details.
            with mock.patch('alot.commands.os.path.expanduser',
                            lambda x: os.path.join(d, x[2:])):
                testfile = os.path.join(d, 'foo')
                with open(testfile, 'w') as f:
                    f.write('foo')

                cmd = envelope.AttachCommand(path='~/foo')
                cmd.apply(ui)
        ui.current_buffer.envelope.attach.assert_called_with(testfile)

    def test_glob(self):
        """A test using a glob."""
        ui = mock.Mock()

        with temporary_directory() as d:
            testfile1 = os.path.join(d, 'foo')
            testfile2 = os.path.join(d, 'far')
            for t in [testfile1, testfile2]:
                with open(t, 'w') as f:
                    f.write('foo')

            cmd = envelope.AttachCommand(path=os.path.join(d, '*'))
            cmd.apply(ui)
        ui.current_buffer.envelope.attach.assert_has_calls(
            [mock.call(testfile1), mock.call(testfile2)], any_order=True)

    def test_no_match(self):
        """A test for a file that doesn't exist."""
        ui = mock.Mock()

        with temporary_directory() as d:
            cmd = envelope.AttachCommand(path=os.path.join(d, 'doesnt-exist'))
            cmd.apply(ui)
        ui.notify.assert_called()


class TestTagCommands(unittest.TestCase):

    def _test(self, tagstring, action, expected):
        """Common steps for envelope.TagCommand tests

        :param tagstring: the string to pass to the TagCommand
        :type tagstring: str
        :param action: the action to pass to the TagCommand
        :type action: str
        :param expected: the expected output to assert in the test
        :type expected: list(str)
        """
        env = Envelope(tags=['one', 'two', 'three'])
        ui = mock.Mock()
        ui.current_buffer = mock.Mock()
        ui.current_buffer.envelope = env
        cmd = envelope.TagCommand(tags=tagstring, action=action)
        cmd.apply(ui)
        actual = env.tags
        self.assertListEqual(sorted(actual), sorted(expected))

    def test_add_new_tags(self):
        self._test(u'four', 'add', ['one', 'two', 'three', 'four'])

    def test_adding_existing_tags_has_no_effect(self):
        self._test(u'one', 'add', ['one', 'two', 'three'])

    def test_remove_existing_tags(self):
        self._test(u'one', 'remove', ['two', 'three'])

    def test_remove_non_existing_tags_has_no_effect(self):
        self._test(u'four', 'remove', ['one', 'two', 'three'])

    def test_set_tags(self):
        self._test(u'a,b,c', 'set', ['a', 'b', 'c'])

    def test_toggle_will_remove_existing_tags(self):
        self._test(u'one', 'toggle', ['two', 'three'])

    def test_toggle_will_add_new_tags(self):
        self._test(u'four', 'toggle', ['one', 'two', 'three', 'four'])

    def test_toggle_can_remove_and_add_in_one_run(self):
        self._test(u'one,four', 'toggle', ['two', 'three', 'four'])
