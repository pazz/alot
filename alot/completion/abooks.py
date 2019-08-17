# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from .completer import Completer
from ..addressbook import AddressbookError
from ..db.utils import formataddr
from ..errors import CompletionError


class AbooksCompleter(Completer):
    """Complete a contact from given address books."""

    def __init__(self, abooks, addressesonly=False):
        """
        :param abooks: used to look up email addresses
        :type abooks: list of :class:`~alot.account.AddresBook`
        :param addressesonly: only insert address, not the realname of the
                              contact
        :type addressesonly: bool
        """
        self.abooks = abooks
        self.addressesonly = addressesonly

    def complete(self, original, pos):
        if not self.abooks:
            return []
        prefix = original[:pos]
        res = []
        for abook in self.abooks:
            try:
                res = res + abook.lookup(prefix)
            except AddressbookError as e:
                raise CompletionError(e)
        if self.addressesonly:
            returnlist = [(addr, len(addr)) for (name, addr) in res]
        else:
            returnlist = []
            for name, addr in res:
                newtext = formataddr((name, addr))
                returnlist.append((newtext, len(newtext)))
        return returnlist
