# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import glob
import os
from .completer import Completer


class PathCompleter(Completer):
    """Completes for file system paths."""

    def complete(self, original, pos):
        if not original:
            return [('~/', 2)]
        prefix = os.path.expanduser(original[:pos])

        def escape(path):
            """Escape all backslashes and spaces in path with a backslash.

            :param path: the path to escape
            :type path: str
            :returns: the escaped path
            :rtype: str
            """
            return path.replace('\\', '\\\\').replace(' ', r'\ ')

        def deescape(escaped_path):
            """Remove escaping backslashes in front of spaces and backslashes.

            :param escaped_path: a path potentially with escaped spaces and
                backslashs
            :type escaped_path: str
            :returns: the actual path
            :rtype: str
            """
            return escaped_path.replace('\\ ', ' ').replace('\\\\', '\\')

        def prep(path):
            escaped_path = escape(path)
            return escaped_path, len(escaped_path)

        return [prep(g) for g in glob.glob(deescape(prefix) + '*')]
