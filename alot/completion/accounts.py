# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import email.utils

from .stringlist import StringlistCompleter
from ..settings.const import settings


class AccountCompleter(StringlistCompleter):
    """Completes users' own mailaddresses."""

    def __init__(self, **kwargs):
        accounts = settings.get_accounts()
        resultlist = [email.utils.formataddr((a.realname, str(a.address)))
                      for a in accounts]
        StringlistCompleter.__init__(self, resultlist, match_anywhere=True,
                                     **kwargs)
