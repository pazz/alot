import re
import os
import shlex

from alot.settings.utils import read_config
from helper import call_cmd


class AddressBook(object):
    """can look up email addresses and realnames for contacts.

    .. note::

        This is an abstract class that leaves :meth:`get_contacts`
        unspecified. See :class:`AbookAddressBook` and
        :class:`MatchSdtoutAddressbook` for implementations.
    """

    def get_contacts(self):
        """list all contacts tuples in this abook as (name, email) tuples"""
        return []

    def lookup(self, prefix=''):
        """looks up all contacts with given prefix (in name or address)"""
        res = []
        for name, email in self.get_contacts():
            if name.startswith(prefix) or email.startswith(prefix):
                res.append((name, email))
        return res


class AbookAddressBook(AddressBook):
    """:class:`AddressBook` that parses abook's config/database files"""
    def __init__(self, path='~/.abook/addressbook'):
        """
        :param path: path to theme file
        :type path: str
        """
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
                if email: res.append((c[id]['name'], email))
        return res


class MatchSdtoutAddressbook(AddressBook):
    """:class:`AddressBook` that parses a shell command's output for lookups"""
    def __init__(self, command, match=None):
        """
        :param command: lookup command
        :type command: str
        :param match: regular expression used to match contacts in `commands`
                      output to stdout. Must define subparts named "email" and
                      "name".  Defaults to
                      :regexp:`^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)`.
        :type match: str
        """
        self.command = command
        if not match:
            self.match = '^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)'
        else:
            self.match = match

    def get_contacts(self):
        return self.lookup('\'\'')

    def lookup(self, prefix):
        cmdlist = shlex.split(self.command.encode('utf-8', errors='ignore'))
        resultstring, errmsg, retval = call_cmd(cmdlist + [prefix])
        if not resultstring:
            return []
        lines = resultstring.splitlines()
        res = []
        for l in lines:
            m = re.match(self.match, l)
            if m:
                info = m.groupdict()
                email = info['email'].strip()
                name = info['name']
                res.append((name, email))
        return res
