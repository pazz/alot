# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse
import re


TRUEISH = ['1', 't', 'true', 'yes', 'on']
FALSISH = ['0', 'f', 'false', 'no', 'off']


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
        kwargs['choices'] = TRUEISH + FALSISH
        kwargs['metavar'] = 'BOOL'
        argparse.Action.__init__(self, *args, **kwargs)
