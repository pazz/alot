# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file


class GPGCode:
    AMBIGUOUS_NAME = 1
    NOT_FOUND = 2
    BAD_PASSPHRASE = 3
    KEY_REVOKED = 4
    KEY_EXPIRED = 5
    KEY_INVALID = 6
    KEY_CANNOT_ENCRYPT = 7
    KEY_CANNOT_SIGN = 8
    INVALID_HASH = 9
    INVALID_HASH_ALGORITHM = 10
    BAD_SIGNATURE = 11


class GPGProblem(Exception):
    """GPG Error"""

    def __init__(self, message, code):
        self.code = code
        super(GPGProblem, self).__init__(message)


class CompletionError(Exception):
    pass


class ConversionError(Exception):
    pass
