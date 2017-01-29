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

"""Tests for alot.utils.argparse"""

from __future__ import absolute_import

import argparse
import contextlib
import os
import shutil
import tempfile
import unittest

import mock

from alot.utils import argparse as cargparse


class TestValidatedStore(unittest.TestCase):
    """Tests for the ValidatedStore action class."""

    def _argparse(self, args):
        """Create an argparse instance with a validator."""

        def validator(args):
            if args == 'fail':
                raise cargparse.ValidationFailed

        parser = argparse.ArgumentParser()
        parser.add_argument(
            'foo',
            action=cargparse.ValidatedStoreAction,
            validator=validator)
        with mock.patch('sys.stderr', mock.Mock()):
            return parser.parse_args(args)

    def test_validates(self):
        # Arparse will raise a SystemExit (calls sys.exit) rather than letting
        # the exception cause the program to close.
        with self.assertRaises(SystemExit):
            self._argparse(['fail'])


@contextlib.contextmanager
def temporary_directory(suffix='', prefix='', dir=None):
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


class TestRequireFile(unittest.TestCase):
    """Tests for the require_file validator."""

    def test_doesnt_exist(self):
        with temporary_directory() as d:
            with self.assertRaises(cargparse.ValidationFailed):
                cargparse.require_file(os.path.join(d, 'doesnt-exist'))

    def test_dir(self):
        with temporary_directory() as d:
            with self.assertRaises(cargparse.ValidationFailed):
                cargparse.require_file(d)

    def test_file(self):
        with tempfile.NamedTemporaryFile() as f:
            cargparse.require_file(f.name)

    def test_char_special(self):
        with self.assertRaises(cargparse.ValidationFailed):
            cargparse.require_file('/dev/null')

    def test_fifo(self):
        with temporary_directory() as d:
            path = os.path.join(d, 'fifo')
            os.mkfifo(path)
            with self.assertRaises(cargparse.ValidationFailed):
                cargparse.require_file(path)


class TestRequireDir(unittest.TestCase):
    """Tests for the require_dir validator."""

    def test_doesnt_exist(self):
        with temporary_directory() as d:
            with self.assertRaises(cargparse.ValidationFailed):
                cargparse.require_dir(os.path.join(d, 'doesnt-exist'))

    def test_dir(self):
        with temporary_directory() as d:
            cargparse.require_dir(d)

    def test_file(self):
        with tempfile.NamedTemporaryFile() as f:
            with self.assertRaises(cargparse.ValidationFailed):
                cargparse.require_dir(f.name)

    def test_char_special(self):
        with self.assertRaises(cargparse.ValidationFailed):
            cargparse.require_dir('/dev/null')

    def test_fifo(self):
        with temporary_directory() as d:
            path = os.path.join(d, 'fifo')
            os.mkfifo(path)
            with self.assertRaises(cargparse.ValidationFailed):
                cargparse.require_dir(path)


class TestOptionalFileLike(unittest.TestCase):
    """Tests for the optional_file_like validator."""

    def test_doesnt_exist(self):
        with temporary_directory() as d:
            cargparse.optional_file_like(os.path.join(d, 'doesnt-exist'))

    def test_dir(self):
        with temporary_directory() as d:
            with self.assertRaises(cargparse.ValidationFailed):
                cargparse.optional_file_like(d)

    def test_file(self):
        with tempfile.NamedTemporaryFile() as f:
            cargparse.optional_file_like(f.name)

    def test_char_special(self):
        cargparse.optional_file_like('/dev/null')

    def test_fifo(self):
        with temporary_directory() as d:
            path = os.path.join(d, 'fifo')
            os.mkfifo(path)
            cargparse.optional_file_like(path)
