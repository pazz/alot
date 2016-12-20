# Copyright (C) 2011-2015  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import re
import abc


class AddressbookError(Exception):
    pass


class AddressBook(object):
    """can look up email addresses and realnames for contacts.

    .. note::

        This is an abstract class that leaves :meth:`get_contacts`
        unspecified. See :class:`AbookAddressBook` and
        :class:`ExternalAddressbook` for implementations.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, ignorecase=True):
        self.reflags = re.IGNORECASE if ignorecase else 0

    @abc.abstractmethod
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
