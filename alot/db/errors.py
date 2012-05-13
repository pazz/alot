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

