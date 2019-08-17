# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from .multipleselection import MultipleSelectionCompleter
from .tag import TagCompleter


class TagsCompleter(MultipleSelectionCompleter):
    """Complete a comma separated list of tagstrings."""

    def __init__(self, dbman):
        """
        :param dbman: used to look up available tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        """
        self._completer = TagCompleter(dbman)
        self._separator = ','
