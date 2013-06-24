# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import re
import os

from alot.settings.utils import read_config
from helper import call_cmd
from alot.helper import split_commandstring


class AddressbookError(Exception):
    pass


class AddressBook(object):
    """can look up email addresses and realnames for contacts.

    .. note::

        This is an abstract class that leaves :meth:`get_contacts`
        unspecified. See :class:`AbookAddressBook` and
        :class:`MatchSdtoutAddressbook` for implementations.
    """
    def __init__(self, ignorecase=True):
        self.reflags = re.IGNORECASE if ignorecase else 0

    def get_contacts(self):
        """list all contacts tuples in this abook as (name, email) tuples"""
        return []

    def lookup(self, query=''):
        """looks up all contacts where name or address match query"""
        res = []
        query = '.*%s.*' % query
        for name, email in self.get_contacts():
            try:
                if re.match(query, name, self.reflags) or \
                        re.match(query, email, self.reflags):
                    res.append((name, email))
            except:
                pass
        return res


class AbookAddressBook(AddressBook):
    """:class:`AddressBook` that parses abook's config/database files"""
    def __init__(self, path='~/.abook/addressbook', **kwargs):
        """
        :param path: path to theme file
        :type path: str
        """
        AddressBook.__init__(self, **kwargs)
        DEFAULTSPATH = os.path.join(os.path.dirname(__file__), 'defaults')
        self._spec = os.path.join(DEFAULTSPATH, 'abook_contacts.spec')
        path = os.path.expanduser(path)
        self._config = read_config(path, self._spec)
        del(self._config['format'])

    def get_contacts(self):
        c = self._config
        res = []
        for id in c.sections:
            for email in c[id]['email']:
                if email:
                    res.append((c[id]['name'], email))
        return res


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
