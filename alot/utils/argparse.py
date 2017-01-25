# encoding=utf-8
# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>

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


TRUEISH = ['true', 'yes', 'on', '1', 't', 'y']
FALSISH = ['false', 'no', 'off', '0', 'f', 'n']


def boolean(string):
    string = string.lower()
    if string in FALSISH:
        return False
    elif string in TRUEISH:
        return True
    else:
        raise ValueError()


class BooleanAction(argparse.Action):
    """
    argparse action that can be used to store boolean values
    """
    def __init__(self, *args, **kwargs):
        kwargs['type'] = boolean
        kwargs['metavar'] = 'BOOL'
        argparse.Action.__init__(self, *args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
