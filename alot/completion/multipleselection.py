# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file


from .completer import Completer


class MultipleSelectionCompleter(Completer):
    """
    Meta-Completer that turns any Completer into one that deals with a list of
    completion strings using the wrapped Completer.
    This allows for example to easily construct a completer for comma separated
    recipient-lists using a :class:`ContactsCompleter`.
    """

    def __init__(self, completer, separator=', '):
        """
        :param completer: completer to use for individual substrings
        :type completer: Completer
        :param separator: separator used to split the completion string into
                          substrings to be fed to `completer`.
        :type separator: str
        """
        self._completer = completer
        self._separator = separator

    def relevant_part(self, original, pos):
        """Calculate the subword of `original` that `pos` is in."""
        start = original.rfind(self._separator, 0, pos)
        if start == -1:
            start = 0
        else:
            start = start + len(self._separator)
        end = original.find(self._separator, pos - 1)
        if end == -1:
            end = len(original)
        return original[start:end], start, end, pos - start

    def complete(self, original, pos):
        mypart, start, end, mypos = self.relevant_part(original, pos)
        res = []
        for c, _ in self._completer.complete(mypart, mypos):
            newprefix = original[:start] + c
            if not original[end:].startswith(self._separator):
                newprefix += self._separator
            res.append((newprefix + original[end:], len(newprefix)))
        return res
