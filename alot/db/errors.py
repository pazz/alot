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


class GPGProblem(Exception):
    """A GPG occured while constructing your mail"""
    pass
