# Copyright (C) 2011-2015  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import re

from ..helper import call_cmd
from ..helper import split_commandstring
from . import AddressBook, AddressbookError


class ExternalAddressbook(AddressBook):
    """:class:`AddressBook` that parses a shell command's output"""

    def __init__(self, commandline, regex, reflags=0,
                 external_filtering=True,
                 **kwargs):
        """
        :param commandline: commandline
        :type commandline: str
        :param regex: regular expression used to match contacts in `commands`
                      output to stdout. Must define subparts named "email" and
                      "name".
        :type regex: str
        :param reflags: flags to use with regular expression.
                        Use the constants defined in :mod:`re` here
                        (`re.IGNORECASE` etc.)
        :type reflags: str
        :param external_filtering: if True the command is fired
                        with the given search string as parameter
                        and the result is not filtered further.
                        If set to False, the command is fired without
                        additional parameters and the result list is filtered
                        according to the search string.
        :type external_filtering: bool
        """
        AddressBook.__init__(self, **kwargs)
        self.commandline = commandline
        self.regex = regex
        self.reflags = reflags
        self.external_filtering = external_filtering

    def get_contacts(self):
        return self._call_and_parse(self.commandline)

    def lookup(self, prefix):
        if self.external_filtering:
            return self._call_and_parse(self.commandline + " " + prefix)
        else:
            return AddressBook.lookup(self, prefix)

    def _call_and_parse(self, commandline):
        cmdlist = split_commandstring(commandline)
        resultstring, errmsg, retval = call_cmd(cmdlist)
        if retval != 0:
            msg = 'abook command "%s" returned with ' % commandline
            msg += 'return code %d' % retval
            if errmsg:
                msg += ':\n%s' % errmsg
            raise AddressbookError(msg)

        if not resultstring:
            return []
        lines = resultstring.splitlines()
        res = []
        for l in lines:
            m = re.match(self.regex, l, self.reflags)
            if m:
                info = m.groupdict()
                if 'email' in info and 'name' in info:
                    email = info['email'].strip()
                    name = info['name']
                    res.append((name, email))
        return res
