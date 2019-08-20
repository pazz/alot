# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from collections.abc import Set

# for backward compatibility with Python <3.7
from collections import OrderedDict


class OrderedSet(Set):
    """
    Ordered collection of distinct hashable objects.
    Taken from https://stackoverflow.com/a/10006674
    """

    def __init__(self, iterable=()):
        self.d = OrderedDict.fromkeys(iterable)

    def __len__(self):
        return len(self.d)

    def __contains__(self, element):
        return element in self.d

    def __iter__(self):
        return iter(self.d)

    def __repr__(self):
        return str(list(self))
