# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import re

from .completer import Completer


class StringlistCompleter(Completer):
    """Completer for a fixed list of strings."""

    def __init__(self, resultlist, ignorecase=True, match_anywhere=False):
        """
        :param resultlist: strings used for completion
        :type resultlist: list of str
        :param liberal: match case insensitive and not prefix-only
        :type liberal: bool
        """
        self.resultlist = resultlist
        self.flags = re.IGNORECASE if ignorecase else 0
        self.match_anywhere = match_anywhere

    def complete(self, original, pos):
        pref = original[:pos]

        re_prefix = '.*' if self.match_anywhere else ''

        def match(s, m):
            r = '{}{}.*'.format(re_prefix, re.escape(m))
            return re.match(r, s, flags=self.flags) is not None

        return [(a, len(a)) for a in self.resultlist if match(a, pref)]
