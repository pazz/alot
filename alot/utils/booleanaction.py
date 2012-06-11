"""
This defines the ConfigureAction for argparse found here:
http://code.google.com/p/argparse/issues/detail?id=2#c6

We use it to set booelan arguments for command parameters
to False using a `--no-` prefix.
"""
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
    def __init__(self, *args, **kwargs):
        kwargs['type'] = boolean
        kwargs['choices'] = TRUEISH + FALSISH
        kwargs['metavar'] = 'BOOL'
        argparse.Action.__init__(self, *args, **kwargs)
