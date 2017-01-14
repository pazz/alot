# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
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
