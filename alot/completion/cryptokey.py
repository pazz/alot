# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from alot import crypto
from .stringlist import StringlistCompleter


class CryptoKeyCompleter(StringlistCompleter):
    """completion for gpg keys"""

    def __init__(self, private=False):
        """
        :param private: return private keys
        :type private: bool
        """
        keys = crypto.list_keys(private=private)
        resultlist = []
        for k in keys:
            for s in k.subkeys:
                resultlist.append(s.keyid)
            for u in k.uids:
                resultlist.append(u.email)
        StringlistCompleter.__init__(self, resultlist, match_anywhere=True)
