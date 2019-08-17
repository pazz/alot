# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from .completer import Completer
from .command import CommandCompleter
from ..helper import split_commandline


class CommandLineCompleter(Completer):
    """completes command lines: semicolon separated command strings"""

    def __init__(self, dbman, mode, currentbuffer=None):
        """
        :param dbman: used to look up available tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        :param mode: mode identifier
        :type mode: str
        :param currentbuffer: currently active buffer. If defined, this will be
                              used to dynamically extract possible completion
                              strings
        :type currentbuffer: :class:`~alot.buffers.Buffer`
        """
        self._commandcompleter = CommandCompleter(dbman, mode, currentbuffer)

    @staticmethod
    def get_context(line, pos):
        """
        computes start and end position of substring of line that is the
        command string under given position
        """
        commands = split_commandline(line) + ['']
        i = 0
        start = 0
        end = len(commands[i])
        while pos > end:
            i += 1
            start = end + 1
            end += 1 + len(commands[i])
        return start, end

    def complete(self, original, pos):
        cstart, cend = self.get_context(original, pos)
        before = original[:cstart]
        after = original[cend:]
        cmdstring = original[cstart:cend]
        cpos = pos - cstart

        res = []
        for ccmd, ccpos in self._commandcompleter.complete(cmdstring, cpos):
            newtext = before + ccmd + after
            newpos = pos + (ccpos - cpos)
            res.append((newtext, newpos))
        return res
