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
import os

import command


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
        self._contactscompleter = ContactsCompleter()
        self._tagscompleter = TagsCompleter(dbman)
        self.keywords = ['tag', 'from', 'to', 'subject', 'attachment',
                         'is', 'id', 'thread', 'folder']

    def complete(self, original):
        prefix = original.split(' ')[-1]
        m = re.search('(tag|is|to):(\w*)', prefix)
        if m:
            cmd, params = m.groups()
            if cmd == 'to':
                return self._contactscompleter.complete(params)
            else:
                return self._tagscompleter.complete(params, last=True)
        else:
            plen = len(prefix)
            matched = filter(lambda t: t.startswith(prefix), self.keywords)
            return [t[plen:] + ':' for t in matched]


class TagsCompleter(Completer):
    """completion for a comma separated list of tagstrings"""

    def __init__(self, dbman):
        self.dbman = dbman

    def complete(self, original, last=False):
        otags = original.split(',')
        prefix = otags[-1]
        tags = self.dbman.get_all_tags()
        if len(otags) > 1 and last:
            return []
        else:
            matching = [t[len(prefix):] for t in tags if t.startswith(prefix)]
            if last:
                return matching
            else:
                return [t + ',' for t in matching]


class ContactsCompleter(Completer):
    """completes contacts"""

    def complete(self, prefix):
        # TODO
        return []


class AccountCompleter(Completer):
    """completes own mailaddresses"""

    def __init__(self, accountman):
        self.accountman = accountman

    def complete(self, prefix):
        valids = self.accountman.get_account_addresses()
        return [a[len(prefix):] for a in valids if a.startswith(prefix)]


class CommandCompleter(Completer):
    """completes commands"""

    def __init__(self, dbman, mode):
        self.dbman = dbman
        self.mode = mode

    def complete(self, original):
        #TODO refine <tab> should get current querystring
        cmdlist = command.ALLOWED_COMMANDS[self.mode]
        olen = len(original)
        return [t[olen:] + '' for t in cmdlist if t.startswith(original)]


class CommandLineCompleter(Completer):
    """completion for commandline"""

    def __init__(self, dbman, accountman, mode):
        self.dbman = dbman
        self.accountman = accountman
        self.mode = mode
        self._commandcompleter = CommandCompleter(dbman, mode)
        self._querycompleter = QueryCompleter(dbman)
        self._tagscompleter = TagsCompleter(dbman)
        self._contactscompleter = ContactsCompleter()
        self._pathcompleter = PathCompleter()

    def complete(self, prefix):
        words = prefix.split(' ', 1)
        if len(words) <= 1:  # we complete commands
            return self._commandcompleter.complete(prefix)
        else:
            cmd, params = words
            if cmd in ['search', 'refine']:
                return self._querycompleter.complete(params)
            if cmd == 'retag':
                return self._tagscompleter.complete(params)
            if cmd == 'toggletag':
                return self._tagscompleter.complete(params, last=True)
            if cmd == 'to':
                return self._contactscompleter.complete(params)
            if cmd == 'edit':
                return self._pathcompleter.complete(params)
            else:
                return []


class PathCompleter(Completer):
    """completion for paths"""
    def complete(self, prefix):
        prep = ''
        if not prefix:
            prefix = '~/'
            prep = '~/'
        dir = os.path.expanduser(os.path.dirname(prefix))
        fileprefix = os.path.basename(prefix)
        res = []
        for f in os.listdir(dir):
            if f.startswith(fileprefix):
                res.append(os.path.join(prep, f[len(fileprefix):]))
        return res
