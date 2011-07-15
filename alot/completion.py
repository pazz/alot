"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""

import re

from alot.command import commands


class Completer:
    def complete(self, original):
        """takes a string that's the prefix of a word,
        returns a list of suffix-strings that complete the original"""
        return list()


class QueryCompleter(Completer):
    """completion for a notmuch query string"""
    # TODO: boolean connectors and braces?
    def __init__(self, dbman):
        self.dbman = dbman
        self.keywords = ['tag', 'from', 'to', 'subject', 'attachment',
                         'is', 'id', 'thread', 'folder']

    def complete(self, original):
        lastbit = prefix = original.split(' ')[-1]
        m = re.findall('[tag|is]:(\w*)', lastbit)
        if m:
            prefix = m[0]
            tags = self.dbman.get_all_tags()
            return [t[len(prefix):] + ' ' for t in tags if t.startswith(prefix)]
        else:
            prefix = original.split(' ')[-1]
            return [t[len(prefix):] + ':' for t in self.keywords if t.startswith(prefix)]


class TagListCompleter(Completer):
    """completion for a comma separated list of tagstrings"""

    def __init__(self, dbman):
        self.dbman = dbman

    def complete(self, original):
        taglist = original.split(',')
        prefix = taglist[-1]
        tags = self.dbman.get_all_tags()
        return [t[len(prefix):] + ',' for t in tags if t.startswith(prefix)]


class CommandCompleter(Completer):
    """completion for commandline"""

    def complete(self, original):
        cmdlist = commands.keys()

        return [t[len(original):] + ' ' for t in cmdlist if t.startswith(original)]
