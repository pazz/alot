# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from .stringlist import StringlistCompleter


class NamedQueryCompleter(StringlistCompleter):
    """Complete the name of a named query string."""

    def __init__(self, dbman):
        """
        :param dbman: used to look up named query strings in the DB
        :type dbman: :class:`~alot.db.DBManager`
        """
        # mapping of alias to query string (dict str -> str)
        nqueries = dbman.get_named_queries()
        StringlistCompleter.__init__(self, list(nqueries))
