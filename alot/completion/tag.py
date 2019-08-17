# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from .stringlist import StringlistCompleter


class TagCompleter(StringlistCompleter):
    """Complete a tagstring."""

    def __init__(self, dbman):
        """
        :param dbman: used to look up available tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        """
        resultlist = dbman.get_all_tags()
        StringlistCompleter.__init__(self, resultlist)
