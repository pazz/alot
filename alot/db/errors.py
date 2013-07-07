# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file


class DatabaseError(Exception):
    pass


class DatabaseROError(DatabaseError):

    """cannot write to read-only database"""
    pass


class DatabaseLockedError(DatabaseError):

    """cannot write to locked index"""
    pass


class NonexistantObjectError(DatabaseError):

    """requested thread or message does not exist in the index"""
    pass
