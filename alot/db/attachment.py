# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os
import tempfile
import email.charset as charset
from copy import deepcopy
from email.message import Message
from typing import IO, cast

from ..helper import humanize_size, guess_mimetype
from .utils import decode_header

charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')


class Attachment:
    """represents a mail attachment"""

    def __init__(self, emailpart: Message) -> None:
        """
        :param emailpart: a non-multipart email that is the attachment
        """
        self.part = emailpart

    def __str__(self) -> str:
        return '%s:%s (%s)' % (self.get_content_type(),
                               self.get_filename(),
                               humanize_size(self.get_size()))

    def get_filename(self) -> str | None:
        """
        return name of attached file.
        If the content-disposition header contains no file name,
        this returns `None`
        """
        fname = self.part.get_filename()
        if fname:
            extracted_name = decode_header(fname)
            if extracted_name:
                return os.path.basename(extracted_name)
        return None

    def get_content_type(self) -> str:
        """mime type of the attachment part"""
        ctype = self.part.get_content_type()
        # replace underspecified mime description by a better guess
        if ctype in ['octet/stream', 'application/octet-stream',
                     'application/octetstream']:
            ctype = guess_mimetype(self.get_data())
        return ctype

    def get_size(self) -> int:
        """returns attachments size in bytes"""
        return len(self.part.get_payload())

    def save(self, path: str) -> str:
        """
        save the attachment to disk. Uses :meth:`~get_filename` in case path
        is a directory
        """
        filename = self.get_filename()
        path = os.path.expanduser(path)
        file_: IO[bytes]
        if os.path.isdir(path):
            if filename:
                basename = os.path.basename(filename)
                file_ = open(os.path.join(path, basename), "wb")
            else:
                file_ = tempfile.NamedTemporaryFile(delete=False, dir=path)
        else:
            file_ = open(path, "wb")  # this throws IOErrors for invalid path
        self.write(file_)
        file_.close()
        return file_.name

    def write(self, fhandle: IO[bytes]) -> None:
        """writes content to a given filehandle"""
        fhandle.write(self.get_data())

    def get_data(self) -> bytes:
        """return data blob from wrapped file"""
        return cast(bytes, self.part.get_payload(decode=True))

    def get_mime_representation(self) -> Message:
        """returns mime part that constitutes this attachment"""
        return deepcopy(self.part)
