# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import re

from alot.settings.const import settings
from .completer import Completer
from .abooks import AbooksCompleter
from .tag import TagCompleter
from .namedquery import NamedQueryCompleter


class QueryCompleter(Completer):
    """completion for a notmuch query string"""
    def __init__(self, dbman):
        """
        :param dbman: used to look up available tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        """
        self.dbman = dbman
        abooks = settings.get_addressbooks()
        self._abookscompleter = AbooksCompleter(abooks, addressesonly=True)
        self._tagcompleter = TagCompleter(dbman)
        self._nquerycompleter = NamedQueryCompleter(dbman)
        self.keywords = ['tag', 'from', 'to', 'subject', 'attachment',
                         'is', 'id', 'thread', 'folder', 'query']

    def complete(self, original, pos):
        mypart, start, end, mypos = self.relevant_part(original, pos)
        myprefix = mypart[:mypos]
        m = re.search(r'(tag|is|to|from|query):(\w*)', myprefix)
        if m:
            cmd, _ = m.groups()
            cmdlen = len(cmd) + 1  # length of the keyword part including colon
            if cmd in ['to', 'from']:
                localres = self._abookscompleter.complete(mypart[cmdlen:],
                                                          mypos - cmdlen)
            elif cmd in ['query']:
                localres = self._nquerycompleter.complete(mypart[cmdlen:],
                                                          mypos - cmdlen)
            else:
                localres = self._tagcompleter.complete(mypart[cmdlen:],
                                                       mypos - cmdlen)
            resultlist = []
            for ltxt, lpos in localres:
                newtext = original[:start] + cmd + ':' + ltxt + original[end:]
                newpos = start + len(cmd) + 1 + lpos
                resultlist.append((newtext, newpos))
            return resultlist
        else:
            matched = (t for t in self.keywords if t.startswith(myprefix))
            resultlist = []
            for keyword in matched:
                newprefix = original[:start] + keyword + ':'
                resultlist.append((newprefix + original[end:], len(newprefix)))
            return resultlist
