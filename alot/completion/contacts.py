# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from .multipleselection import MultipleSelectionCompleter
from .abooks import AbooksCompleter


class ContactsCompleter(MultipleSelectionCompleter):
    """completes contacts from given address books"""

    def __init__(self, abooks, addressesonly=False):
        """
        :param abooks: used to look up email addresses
        :type abooks: list of :class:`~alot.account.AddresBook`
        :param addressesonly: only insert address, not the realname of the
                              contact
        :type addressesonly: bool
        """
        self._completer = AbooksCompleter(abooks, addressesonly=addressesonly)
        self._separator = ', '
