# encoding=utf-8
# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
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

"""Custom extensions of the argparse module."""

from __future__ import absolute_import

import argparse
import collections
import functools
import itertools
import os
import stat


_TRUEISH = ['true', 'yes', 'on', '1', 't', 'y']
_FALSISH = ['false', 'no', 'off', '0', 'f', 'n']


class ValidationFailed(Exception):
    """Exception raised when Validation fails in a ValidatedStoreAction."""
    pass


def _boolean(string):
    string = string.lower()
    if string in _FALSISH:
        return False
    elif string in _TRUEISH:
        return True
    else:
        raise ValueError('Option must be one of: {}'.format(
            ', '.join(itertools.chain(iter(_TRUEISH), iter(_FALSISH)))))


def _path_factory(check):
    """Create a function that checks paths."""

    @functools.wraps(check)
    def validator(paths):
        if isinstance(paths, str):
            check(paths)
        elif isinstance(paths, collections.Sequence):
            for path in paths:
                check(path)
        else:
            raise Exception('expected either basestr or sequenc of basstr')

    return validator


@_path_factory
def require_file(path):
    """Validator that asserts that a file exists.

    This fails if there is nothing at the given path.
    """
    if not os.path.isfile(path):
        raise ValidationFailed('{} is not a valid file.'.format(path))


@_path_factory
def optional_file_like(path):
    """Validator that ensures that if a file exists it regular, a fifo, or a
    character device. The file is not required to exist.

    This includes character special devices like /dev/null.
    """
    if (os.path.exists(path) and not (os.path.isfile(path) or
                                      stat.S_ISFIFO(os.stat(path).st_mode) or
                                      stat.S_ISCHR(os.stat(path).st_mode))):
        raise ValidationFailed(
            '{} is not a valid file, character device, or fifo.'.format(path))


@_path_factory
def require_dir(path):
    """Validator that asserts that a directory exists.

    This fails if there is nothing at the given path.
    """
    if not os.path.isdir(path):
        raise ValidationFailed('{} is not a valid directory.'.format(path))


def is_int_or_pm(value):
    """Validator to assert that value is '+', '-', or an integer"""
    if value not in ['+', '-']:
        try:
            value = int(value)
        except ValueError:
            raise ValidationFailed('value must be an integer or "+" or "-".')
    return value


class BooleanAction(argparse.Action):
    """Argparse action that can be used to store boolean values."""
    def __init__(self, *args, **kwargs):
        kwargs['type'] = _boolean
        kwargs['metavar'] = 'BOOL'
        argparse.Action.__init__(self, *args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)


class ValidatedStoreAction(argparse.Action):
    """An action that allows a validation function to be specificied.

    The validator keyword must be a function taking exactly one argument, that
    argument is a list of strings or the type specified by the type argument.
    It must raise ValidationFailed with a message when validation fails.
    """

    def __init__(self, option_strings, dest=None, nargs=None, default=None,
                 required=False, type=None, metavar=None, help=None,
                 validator=None):
        super(ValidatedStoreAction, self).__init__(
            option_strings=option_strings, dest=dest, nargs=nargs,
            default=default, required=required, metavar=metavar, type=type,
            help=help)

        self.validator = validator

    def __call__(self, parser, namespace, values, option_string=None):
        if self.validator:
            try:
                self.validator(values)
            except ValidationFailed as e:
                raise argparse.ArgumentError(self, str(e))

        setattr(namespace, self.dest, values)
