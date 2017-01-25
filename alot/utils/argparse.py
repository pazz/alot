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
import itertools


_TRUEISH = ['true', 'yes', 'on', '1', 't', 'y']
_FALSISH = ['false', 'no', 'off', '0', 'f', 'n']


def _boolean(string):
    string = string.lower()
    if string in _FALSISH:
        return False
    elif string in _TRUEISH:
        return True
    else:
        raise ValueError('Option must be one of: {}'.format(
            ', '.join(itertools.chain(iter(_TRUEISH), iter(_FALSISH)))))


class BooleanAction(argparse.Action):
    """Argparse action that can be used to store boolean values."""
    def __init__(self, *args, **kwargs):
        kwargs['type'] = _boolean
        kwargs['metavar'] = 'BOOL'
        argparse.Action.__init__(self, *args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
