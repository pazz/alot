# Copyright (C) 2011-2015  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import re

from ..helper import call_cmd
from ..helper import split_commandstring
from . import AddressBook, AddressbookError


class MatchSdtoutAddressbook(AddressBook):
    """:class:`AddressBook` that parses a shell command's output for lookups"""

    def __init__(self, command, match=None, **kwargs):
        """
        :param command: lookup command
        :type command: str
        :param match: regular expression used to match contacts in `commands`
                      output to stdout. Must define subparts named "email" and
                      "name".  Defaults to
                      :regexp:`^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)`.
        :type match: str
        """
        AddressBook.__init__(self, **kwargs)
        self.command = command
        if not match:
            self.match = '^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)'
        else:
            self.match = match

    def get_contacts(self):
        return self.lookup('\'\'')

    def lookup(self, prefix):
        cmdlist = split_commandstring(self.command)
        resultstring, errmsg, retval = call_cmd(cmdlist + [prefix])
        if retval != 0:
            msg = 'abook command "%s" returned with ' % self.command
            msg += 'return code %d' % retval
            if errmsg:
                msg += ':\n%s' % errmsg
            raise AddressbookError(msg)

        if not resultstring:
            return []
        lines = resultstring.splitlines()
        res = []
        for l in lines:
            m = re.match(self.match, l, self.reflags)
            if m:
                info = m.groupdict()
                if 'email' and 'name' in info:
                    email = info['email'].strip()
                    name = info['name']
                    res.append((name, email))
        return res
