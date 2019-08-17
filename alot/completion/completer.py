# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import abc


class Completer:
    """base class for completers"""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def complete(self, original, pos):
        """returns a list of completions and cursor positions for the string
        `original` from position `pos` on.

        :param original: the string to complete
        :type original: str
        :param pos: starting position to complete from
        :type pos: int
        :returns: pairs of completed string and cursor position in the
                  new string
        :rtype: list of (str, int)
        :raises: :exc:`CompletionError`
        """
        pass

    def relevant_part(self, original, pos):
        """
        Calculate the subword in a ' '-separated list of substrings of
        `original` that `pos` is in.
        """
        start = original.rfind(' ', 0, pos) + 1
        end = original.find(' ', pos - 1)
        if end == -1:
            end = len(original)
        return original[start:end], start, end, pos - start
