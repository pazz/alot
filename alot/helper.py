"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
from datetime import date
from datetime import timedelta

import shlex
import subprocess
import email
import mimetypes
import os
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def shorten(string, maxlen):
    if len(string) > maxlen - 3:
        string = string[:maxlen - 3] + u'\u2026'
    return string


def pretty_datetime(d):
    today = date.today()
    if today == d.date():
        string = d.strftime('%H:%M%P')
    elif d.date() == today - timedelta(1):
        string = 'Yest.%2d' % d.hour + d.strftime('%P')
    elif d.year != today.year:
        string = d.strftime('%b %Y')
    else:
        string = d.strftime('%b %d')
    return string


def cmd_output(command_line):
    args = shlex.split(command_line.encode('ascii', errors='ignore'))
    try:
        output = subprocess.check_output(args)
    except subprocess.CalledProcessError:
        return None
    except OSError:
        return None
    return output


def pipe_to_command(cmd, stdin):
        # no unicode in shlex on 2.x
        args = shlex.split(cmd.encode('ascii'))
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            out, err = proc.communicate(stdin)
        except OSError, e:
            return '', str(e)
        if proc.poll():  # returncode is not 0
            e = 'return value != 0'
            if err.strip():
                e = e + ': %s' % err
            return '', e
        else:
            return out, err


def attach(path, mail, filename=None):
    ctype, encoding = mimetypes.guess_type(path)
    if ctype is None or encoding is not None:
        # No guess could be made, or the file is encoded (compressed),
        # so use a generic bag-of-bits type.
        ctype = 'application/octet-stream'
    maintype, subtype = ctype.split('/', 1)
    if maintype == 'text':
        fp = open(path)
        # Note: we should handle calculating the charset
        part = MIMEText(fp.read(), _subtype=subtype)
        fp.close()
    elif maintype == 'image':
        fp = open(path, 'rb')
        part = MIMEImage(fp.read(), _subtype=subtype)
        fp.close()
    elif maintype == 'audio':
        fp = open(path, 'rb')
        part = MIMEAudio(fp.read(), _subtype=subtype)
        fp.close()
    else:
        fp = open(path, 'rb')
        part = MIMEBase(maintype, subtype)
        part.set_payload(fp.read())
        fp.close()
        # Encode the payload using Base64
        email.encoders.encode_base64(part)
    # Set the filename parameter
    if not filename:
        filename = os.path.basename(path)
    part.add_header('Content-Disposition', 'attachment',
                    filename=filename)
    mail.attach(part)


def shell_quote(text):
    r'''
    >>> print(shell_quote("hello"))
    'hello'
    >>> print(shell_quote("hello'there"))
    'hello'"'"'there'
    '''
    return "'%s'" % text.replace("'", """'"'"'""")
