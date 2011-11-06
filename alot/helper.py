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
from collections import deque
from string import strip
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
import urwid

from settings import config


def string_sanitize(string, tab_width=None):
    r"""
    strips, and replaces non-printable characters

    >>> string_sanitize(' foo\rbar ', 8)
    'foobar'
    >>> string_sanitize('foo\tbar', 8)
    'foo     bar'
    >>> string_sanitize('foo\t\tbar', 8)
    'foo             bar'
    """
    if tab_width == None:
        tab_width = config.getint('general', 'tabwidth')

    string = string.strip()
    string = string.replace('\r', '')

    lines = list()
    for line in string.split('\n'):
        tab_count = line.count('\t')

        if tab_count > 0:
            line_length = 0
            new_line = list()
            for i, chunk in enumerate(line.split('\t')):
                line_length += len(chunk)
                new_line.append(chunk)

                if i < tab_count:
                    next_tab_stop_in = tab_width - (line_length % tab_width)
                    new_line.append(' ' * next_tab_stop_in)
                    line_length += next_tab_stop_in
            lines.append(''.join(new_line))
        else:
            lines.append(line)

    return '\n'.join(lines)


def string_decode(string, enc='ascii'):
    """decodes string to unicode bytestring, respecting enc as a hint"""

    if enc is None:
        enc = 'ascii'
    try:
        string = unicode(string, enc, errors='replace')
    except LookupError:  # malformed enc string
        string = string.decode('ascii', errors='replace')
    except TypeError:  # already unicode
        pass
    return string


def shorten(string, maxlen):
    if maxlen > 1 and len(string) > maxlen:
        string = string[:maxlen - 1] + u'\u2026'
    return string[:maxlen]


def shorten_author_string(authors_string, maxlength):
    """
    Parse a list of authors concatenated as a text string (comma
    separated) and smartly adjust them to maxlength.

    1) If the complete list of sender names does not fit in maxlength, it
    tries to shorten names by using only the first part of each.

    2) If the list is still too long, hide authors according to the
    following priority:

      - First author is always shown (if too long is shorten with ellipsis)

      - If possible, last author is also shown (if too long, uses
        ellipsis)

      - If there are more than 2 authors in the thread, show the
        maximum of them. More recent senders have more priority (Is
        the list of authors already sorted by the date of msgs????)

      - If it is finally necessary to hide any author, an ellipsis
        between first and next authors is added.


    EXAMPLE (authors string with different length constrains):
         'King Kong, Mucho Muchacho, Jaime Huerta, Flash Gordon'
         'King, Mucho, Jaime, Flash'
         'King, ., Jaime, Flash'
         'King, ., J., Flash'
         'King, ., Flash'
         'King, ., Fl.'
         'King, .'
         'K., .'
         'K.'
         """

    # I will create a list of authors by parsing author_string. I use
    # deque to do popleft without performance penalties
    authors = deque()

    # If author list is too long, it uses only the first part of each
    # name (gmail style)
    short_names = len(authors_string) > maxlength
    for au in authors_string.split(", "):
        if short_names:
            authors.append(strip(au.split()[0]))
        else:
            authors.append(au)

    # Author chain will contain the list of author strings to be
    # concatenated using commas for the final formatted author_string.
    authors_chain = deque()

    # reserve space for first author
    first_au = shorten(authors.popleft(), maxlength)
    remaining_length = maxlength - len(first_au)

    # Tries to add an ellipsis if no space to show more than 1 author
    if authors and maxlength > 3 and remaining_length < 3:
        first_au = shorten(first_au, maxlength - 3)
        remaining_length += 3

    # Tries to add as more authors as possible. It takes into account
    # that if any author will be hidden, and ellipsis should be added
    while authors and remaining_length >= 3:
        au = authors.pop()
        if len(au) > 1 and (remaining_length == 3 or
                          (authors and remaining_length < 7)):
            authors_chain.appendleft(u'\u2026')
            break
        else:
            if authors:
                # 5= ellipsis + 2 x comma and space used as separators
                au_string = shorten(au, remaining_length - 5)
            else:
                # 2 = comma and space used as separator
                au_string = shorten(au, remaining_length - 2)
            remaining_length -= len(au_string) + 2
            authors_chain.appendleft(au_string)

    # Add the first author to the list and concatenate list
    authors_chain.appendleft(first_au)
    authorsstring = ', '.join(authors_chain)
    return authorsstring


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
    args = shlex.split(command_line.encode('utf-8', errors='ignore'))
    try:
        output = subprocess.check_output(args)
        output = string_decode(output, urwid.util.detected_encoding)
    except subprocess.CalledProcessError:
        return None
    except OSError:
        return None
    return output


def pipe_to_command(cmd, stdin):
        # remove quotes which have been put around the whole command
        if cmd[0] == '"' and cmd[-1] == '"':
            cmd = cmd[1:-1]
        args = shlex.split(cmd.encode('utf-8', errors='ignore'))
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
    #wrap in multipart if not already
    if not mail.is_multipart():
        newmail = MIMEMultipart()
        #move headers to new outer mail
        for k in mail.keys():
            newmail[k] = mail[k]
            del(mail[k])
        newmail.attach(mail)
        mail = newmail
    mail.attach(part)
    return mail


def shell_quote(text):
    r'''
    >>> print(shell_quote("hello"))
    'hello'
    >>> print(shell_quote("hello'there"))
    'hello'"'"'there'
    '''
    return "'%s'" % text.replace("'", """'"'"'""")


def tag_cmp(a, b):
    r'''
    Sorting tags using this function puts all tags of length 1 at the
    beginning. This groups all tags mapped to unicode characters.
    '''
    if min(len(a), len(b)) == 1:
        return cmp(len(a), len(b))
    else:
        return cmp(a, b)


def humanize_size(size):
    r'''
    >>> humanize_size(1)
    '1'
    >>> humanize_size(123)
    '123'
    >>> humanize_size(1234)
    '1K'
    >>> humanize_size(1234 * 1024)
    '1.2M'
    >>> humanize_size(1234 * 1024 * 1024)
    '1234.0M'
    '''
    for factor, format_string in ((1, '%i'),
                                  (1024, '%iK'),
                                  (1024 * 1024, '%.1fM')):
        if size / factor < 1024:
            return format_string % (float(size) / factor)
    return format_string % (size / factor)
