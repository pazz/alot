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


class Completer:
    def complete(self, original):
        return list()


class QueryCompleter(Completer):
    """completion for a notmuch query string"""

    def __init__(self, dbman):
        self.dbman = dbman

    def complete(self, original):
        m = re.findall('.*tag:(.*)', original)
        if m:
            prefix = m[0]
            tags = self.dbman.get_all_tags()
            return [t[len(prefix):] for t in tags if t.startswith(prefix)]
        else:
            return list()


class TagListCompleter(Completer):
    """completion for a comma separated list of tagstrings"""

    def __init__(self, dbman):
        self.dbman = dbman

    def complete(self, original):
        taglist = original.split(',')
        prefix = taglist[-1]
        tags = self.dbman.get_all_tags()
        return [t[len(prefix):] + ',' for t in tags if t.startswith(prefix)]
