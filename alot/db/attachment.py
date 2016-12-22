# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os
import tempfile
import email.charset as charset
from email.header import Header
from copy import deepcopy

from ..helper import string_decode, humanize_size, guess_mimetype
from .utils import decode_header

charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')


class Attachment(object):

    """represents a mail attachment"""

    def __init__(self, emailpart):
        """
        :param emailpart: a non-multipart email that is the attachment
        :type emailpart: :class:`email.message.Message`
        """
        self.part = emailpart

    def __str__(self):
        desc = '%s:%s (%s)' % (self.get_content_type(),
                               self.get_filename(),
                               humanize_size(self.get_size()))
        return string_decode(desc)

    def get_filename(self):
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

    def get_content_type(self):
        """mime type of the attachment part"""
        ctype = self.part.get_content_type()
        # replace underspecified mime description by a better guess
        if ctype in ['octet/stream', 'application/octet-stream',
                     'application/octetstream']:
            ctype = guess_mimetype(self.get_data())
        return ctype

    def get_size(self):
        """returns attachments size in bytes"""
        return len(self.part.get_payload())

    def save(self, path):
        """
        save the attachment to disk. Uses :meth:`~get_filename` in case path
        is a directory
        """
        filename = self.get_filename()
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            if filename:
                basename = os.path.basename(filename)
                file_ = open(os.path.join(path, basename), "w")
            else:
                file_ = tempfile.NamedTemporaryFile(delete=False, dir=path)
        else:
            file_ = open(path, "w")  # this throws IOErrors for invalid path
        self.write(file_)
        file_.close()
        return file_.name

    def write(self, fhandle):
        """writes content to a given filehandle"""
        fhandle.write(self.get_data())

    def get_data(self):
        """return data blob from wrapped file"""
        return self.part.get_payload(decode=True)

    def get_mime_representation(self):
        """returns mime part that constitutes this attachment"""
        part = deepcopy(self.part)
        cd = self.part['Content-Disposition']
        del part['Content-Disposition']
        part['Content-Disposition'] = Header(cd, maxlinelen=78,
                                             header_name='Content-Disposition')
        return part
