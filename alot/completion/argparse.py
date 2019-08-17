# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import argparse
from .completer import Completer
from ..utils import argparse as cargparse


class ArgparseOptionCompleter(Completer):
    """completes option parameters for a given argparse.Parser"""
    def __init__(self, parser):
        """
        :param parser: the option parser we look up parameter and  choices from
        :type parser: `argparse.ArgumentParser`
        """
        self.parser = parser
        self.actions = parser._optionals._actions

    def complete(self, original, pos):
        pref = original[:pos]

        res = []
        for act in self.actions:
            if '=' in pref:
                optionstring = pref[:pref.rfind('=') + 1]
                # get choices
                if 'choices' in act.__dict__:
                    # TODO: respect prefix
                    choices = act.choices or []
                    res = res + [optionstring + a for a in choices]
            else:
                for optionstring in act.option_strings:
                    if optionstring.startswith(pref):
                        # append '=' for options that await a string value
                        if isinstance(act, (argparse._StoreAction,
                                            cargparse.BooleanAction)):
                            optionstring += '='
                        res.append(optionstring)

        return [(a, len(a)) for a in res]
