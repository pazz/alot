import os
import tempfile
import email.charset as charset
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')
import alot.helper as helper
from alot.helper import string_decode

from alot.db.utils import decode_header


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
                              helper.humanize_size(self.get_size()))
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
        if ctype in ['octet/stream', 'application/octet-stream']:
            ctype = helper.guess_mimetype(self.get_data())
        return ctype

    def get_size(self):
        """returns attachments size in bytes"""
        return len(self.part.get_payload())

    def save(self, path):
        """
        save the attachment to disk. Uses :meth:`get_filename` in case path
        is a directory
        """
        filename = self.get_filename()
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            if filename:
                basename = os.path.basename(filename)
                FILE = open(os.path.join(path, basename), "w")
            else:
                FILE = tempfile.NamedTemporaryFile(delete=False, dir=path)
        else:
            FILE = open(path, "w")  # this throws IOErrors for invalid path
        self.write(FILE)
        FILE.close()
        return FILE.name

    def write(self, fhandle):
        """writes content to a given filehandle"""
        fhandle.write(self.get_data())

    def get_data(self):
        """return data blob from wrapped file"""
        return self.part.get_payload(decode=True)

    def get_mime_representation(self):
        """returns mime part that constitutes this attachment"""
        return self.part
