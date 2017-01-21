# Copyright (C) 2011-2015  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import os
from . import AddressBook
from ..settings.utils import read_config


class AbookAddressBook(AddressBook):
    """:class:`AddressBook` that parses abook's config/database files"""
    def __init__(self, path='~/.abook/addressbook', **kwargs):
        """
        :param path: path to abook addressbook file
        :type path: str
        """
        AddressBook.__init__(self, **kwargs)
        DEFAULTSPATH = os.path.join(os.path.dirname(__file__), '..', 'defaults')
        self._spec = os.path.join(DEFAULTSPATH, 'abook_contacts.spec')
        path = os.path.expanduser(path)
        self._config = read_config(path, self._spec)
        del self._config['format']

    def get_contacts(self):
        c = self._config
        res = []
        for id in c.sections:
            for email in c[id]['email']:
                if email:
                    res.append((c[id]['name'], email))
        return res
