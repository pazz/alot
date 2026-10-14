# -*- coding: utf-8 -*-
# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2017-2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import atexit
from datetime import timedelta
from datetime import datetime
from collections import deque
import locale
import logging
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import email
import functools
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import asyncio
from typing import TYPE_CHECKING

import magic

if TYPE_CHECKING:
    from alot.db.envelope import Envelope


def split_commandline(s: str) -> list[str]:
    """
    splits semi-colon separated commandlines, ignoring quoted separators
    """
    splitter = r'''((?:[^;"']|"(\\\\|\\"|[^"])*(?:"|$)|'(\\\\|\\'|[^'])*(?:'|$))+)'''
    return re.split(splitter, s)[1::4]


def unicode_printable(c: str) -> bool:
    """
    Checks if the given character is a printable Unicode character, i.e., not a
    private/unassigned character and not a control character other than tab or
    newline.
    """
    if c in ('\n', '\t'):
        return True
    return unicodedata.category(c) not in ('Cc', 'Cn', 'Co')


def string_sanitize(string: str) -> str:
    r"""
    strips non-printable characters and expands tabs to 8 columns

    >>> string_sanitize(' foo\rbar ')
    ' foobar '
    >>> string_sanitize('foo\tbar')
    'foo     bar'
    >>> string_sanitize('foo\t\tbar')
    'foo             bar'
    """

    preprocessed_string = ''
    i = 0
    while i < len(string):
        # Check if this is the start of an allowed ANSI escape sequence. For
        # security reasons, we only allow SGR (Select Graphic Rendition)
        # parameters; i.e., sequences used for basic formatting such as
        # coloring and font variants.
        if string[i:i + 2] == '\x1b[':
            j = i + 2
            # Skip over all "parameter bytes" and "intermediate bytes"
            for skip_chars in ('0123456789:;<=>?', ' !"#$%&\'()*+,-./'):
                while j < len(string) and string[j] in skip_chars:
                    j += 1
            # Keep only SGR sequences in the preprocessed string
            if j < len(string) and string[j] == 'm':
                preprocessed_string += string[i:j + 1]
            i = j + 1
            continue

        # Not a valid ANSI escape sequence, only allow printable characters.
        if unicode_printable(string[i]):
            preprocessed_string += string[i]
        i += 1

    return preprocessed_string.expandtabs(8)


def string_decode(string: str | bytes, enc: str | None = 'ascii') -> str:
    """
    safely decodes bytes to str, respecting `enc` as a hint.

    :param enc: a hint what encoding is used in string ('ascii', 'utf-8', ...)
    """
    if isinstance(string, str):
        return string
    try:
        return string.decode(enc or 'ascii', errors='replace')
    except LookupError:  # malformed enc string
        return string.decode('ascii', errors='replace')


def shorten(string: str, maxlen: int) -> str:
    """shortens string if longer than maxlen, appending ellipsis"""
    if 1 < maxlen < len(string):
        string = string[:maxlen - 1] + '…'
    return string[:maxlen]


def shorten_author_string(authors_string: str, maxlength: int) -> str:
    """
    Parse a list of authors concatenated as a text string (comma
    separated) and smartly adjust them to maxlength.

    1) If the complete list of sender names does not fit in maxlength, it
    tries to shorten names by using only the first part of each.

    2) If the list is still too long, hide authors according to the
    following priority:

      - First author is always shown (if too long is shorten with ellipsis)

      - If possible, last author is also shown (if too long, uses ellipsis)

      - If there are more than 2 authors in the thread, show the
        maximum of them. More recent senders have higher priority.

      - If it is finally necessary to hide any author, an ellipsis
        between first and next authors is added.
    """

    # I will create a list of authors by parsing author_string. I use
    # deque to do popleft without performance penalties
    authors: deque[str] = deque()

    # If author list is too long, it uses only the first part of each
    # name (gmail style)
    short_names = len(authors_string) > maxlength
    for au in authors_string.split(", "):
        if short_names:
            author_as_list = au.split()
            if len(author_as_list) > 0:
                authors.append(author_as_list[0])
        else:
            authors.append(au)

    # Author chain will contain the list of author strings to be
    # concatenated using commas for the final formatted author_string.
    authors_chain: deque[str] = deque()

    if len(authors) == 0:
        return ''

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
        if len(au) > 1 and (remaining_length == 3 or (authors and
                                                      remaining_length < 7)):
            authors_chain.appendleft('…')
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


def pretty_datetime(d: datetime) -> str:
    """
    translates :class:`datetime` `d` to a "sup-style" human readable string,
    such as 'just now', '1min ago', '5h ago', '02:54am', 'yest 02pm',
    'Thu 02pm', 'Mar 24' or 'Apr 2011', depending on how long ago `d` was.
    """
    ampm = d.strftime('%p').lower()
    if len(ampm):
        hourfmt = '%I' + ampm
        hourminfmt = '%I:%M' + ampm
    else:
        hourfmt = '%Hh'
        hourminfmt = '%H:%M'

    now = datetime.now()
    today = now.date()
    if d.date() == today or d > now - timedelta(hours=6):
        delta = datetime.now() - d
        if delta.seconds < 60:
            string = 'just now'
        elif delta.seconds < 3600:
            string = '%dmin ago' % (delta.seconds // 60)
        elif delta.seconds < 6 * 3600:
            string = '%dh ago' % (delta.seconds // 3600)
        else:
            string = d.strftime(hourminfmt)
    elif d.date() == today - timedelta(1):
        string = d.strftime('yest ' + hourfmt)
    elif d.date() > today - timedelta(7):
        string = d.strftime('%a ' + hourfmt)
    elif d.year != today.year:
        string = d.strftime('%b %Y')
    else:
        string = d.strftime('%b %d')
    return string


def call_cmd(cmdlist: list[str],
             stdin: str | bytes | None = None) -> tuple[str, str, int]:
    """
    get a shell commands output, error message and return value and immediately
    return.

    .. warning::

        This returns with the first screen content for interactive commands.

    :param cmdlist: shellcommand to call, already splitted into a list accepted
                    by :meth:`subprocess.Popen`
    :param stdin: string to pipe to the process
    :return: triple of stdout, stderr, return value of the shell command
    """
    termenc = locale.getpreferredencoding(False)
    if isinstance(stdin, str):
        stdin = stdin.encode(termenc)
    logging.debug("Calling %s" % cmdlist)
    try:
        proc = subprocess.run(cmdlist, input=stdin, capture_output=True)
    except OSError as e:
        return '', e.strerror or str(e), e.errno or 1
    return (string_decode(proc.stdout, termenc),
            string_decode(proc.stderr, termenc), proc.returncode)


async def call_cmd_async(cmdlist: list[str],
                         stdin: str | None = None) -> tuple[str, str, int]:
    """Given a command, call that command asynchronously and return the output.

    This function only handles `OSError` when creating the subprocess, any
    other exceptions raised either durring subprocess creation or while
    exchanging data with the subprocess are the caller's responsibility to
    handle.

    If such an `OSError` is caught, then returncode will be set to 1, and the
    error value will be set to the str() value of the exception.

    :param stdin: string to pipe to the process
    :return: Tuple of stdout, stderr, returncode
    """
    termenc = locale.getpreferredencoding(False)
    args = [s.encode(termenc) for s in cmdlist]

    logging.debug('CMD = %s', args)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if stdin else None)
    except OSError as e:
        return ('', str(e), 1)
    out, err = await proc.communicate(stdin.encode(termenc) if stdin else None)
    return (out.decode(termenc), err.decode(termenc), await proc.wait())


def guess_mimetype(blob: bytes) -> str:
    """
    uses file magic to determine the mime-type of the given data blob.

    :param blob: file content as read by file.read()
    :returns: mime-type, falls back to 'application/octet-stream'
    """
    mimetype = 'application/octet-stream'
    # this is a bit of a hack to support different versions of python magic.
    # Hopefully at some point this will no longer be necessary
    #
    # the version with open() is the bindings shipped with the file source from
    # https://darwinsys.com/file/ - this is what is used by the python-magic
    # package on Debian/Ubuntu. However, it is not available on pypi/via pip.
    #
    # the version with from_buffer() is available at
    # https://github.com/ahupp/python-magic and directly installable via pip.
    #
    # for more detail see https://github.com/pazz/alot/pull/588
    if hasattr(magic, 'open'):
        m = magic.open(magic.MAGIC_MIME_TYPE)
        m.load()
        magictype = m.buffer(blob) or mimetype
    elif hasattr(magic, 'from_buffer'):
        # cf. issue #841
        magictype = magic.from_buffer(blob, mime=True) or mimetype
    else:
        raise Exception('Unknown magic API')

    # libmagic does not always return proper mimetype strings, cf. issue #459
    if re.match(r'\w+\/\w+', magictype):
        mimetype = magictype
    return mimetype


def guess_encoding(blob: bytes) -> str:
    """
    uses file magic to determine the encoding of the given data blob.

    :param blob: file content as read by file.read()
    """
    # this is a bit of a hack to support different versions of python magic.
    # Hopefully at some point this will no longer be necessary
    #
    # the version with open() is the bindings shipped with the file source from
    # https://darwinsys.com/file/ - this is what is used by the python-magic
    # package on Debian/Ubuntu.  However it is not available on pypi/via pip.
    #
    # the version with from_buffer() is available at
    # https://github.com/ahupp/python-magic and directly installable via pip.
    #
    # for more detail see https://github.com/pazz/alot/pull/588
    if hasattr(magic, 'open'):
        m = magic.open(magic.MAGIC_MIME_ENCODING)
        m.load()
        enc: str = m.buffer(blob)
    elif hasattr(magic, 'from_buffer'):
        enc = magic.Magic(mime_encoding=True).from_buffer(blob)
    else:
        raise Exception('Unknown magic API')
    return enc


def try_decode(blob: bytes) -> str:
    """Guess the encoding of blob and try to decode it into a str."""
    assert isinstance(blob, bytes), 'cannot decode a str or non-bytes object'
    enc = guess_encoding(blob)
    try:
        return blob.decode(enc)
    except (LookupError, UnicodeDecodeError):
        logging.warning('cannot decode as %s, falling back to utf-8', enc)
        return blob.decode('utf-8', errors='replace')


# TODO: make this work on blobs, not paths
def mimewrap(path: str, filename: str | None = None,
             ctype: str | None = None) -> MIMEBase:
    """Take the contents of the given path and wrap them into an email MIME
    part according to the content type.  The content type is auto detected from
    the actual file contents and the file name if it is not given.

    :param path: the path to the file contents
    :param filename: the file name to use in the generated MIME part
    :param ctype: the content type of the file contents in path
    :returns: the message MIME part storing the data from path
    """

    with open(path, 'rb') as f:
        content = f.read()
    ctype = ctype or guess_mimetype(content)
    maintype, subtype = ctype.split('/', 1)
    if maintype == 'text':
        part: MIMEBase = MIMEText(
            content.decode(guess_encoding(content), 'replace'),
            _subtype=subtype, _charset='utf-8')
    elif maintype == 'image':
        part = MIMEImage(content, _subtype=subtype)
    elif maintype == 'audio':
        part = MIMEAudio(content, _subtype=subtype)
    else:
        part = MIMEBase(maintype, subtype)
        part.set_payload(content)
        # Encode the payload using Base64
        email.encoders.encode_base64(part)
    # Set the filename parameter
    if not filename:
        filename = os.path.basename(path)
    part.add_header('Content-Disposition', 'attachment',
                    filename=filename)
    return part


def humanize_size(size: int) -> str:
    """Create a nice human readable representation of the given number
    (understood as bytes) using the "KiB" and "MiB" suffixes to indicate
    kibibytes and mebibytes. A kibibyte is defined as 1024 bytes (as opposed to
    a kilobyte which is 1000 bytes) and a mibibyte is 1024**2 bytes (as opposed
    to a megabyte which is 1000**2 bytes).

    :param size: the number to convert
    :returns: the human readable representation of size
    """
    for factor, format_string in ((1, '%i'),
                                  (1024, '%iKiB'),
                                  (1024 * 1024, '%.1fMiB')):
        if size / factor < 1024:
            return format_string % (size / factor)
    return format_string % (size / factor)


def parse_mailcap_nametemplate(tmplate: str = '%s') -> tuple[str, str]:
    """this returns a prefix and suffix to be used
    in the tempfile module for a given mailcap nametemplate string"""
    nt_list = tmplate.split('%s')
    return (nt_list[0], nt_list[1]) if len(nt_list) == 2 else ('', tmplate)


def parse_mailto(mailto_str: str) -> (
        tuple[dict[str, list[str]], str] | tuple[None, None]):
    """
    Interpret mailto-string

    :param mailto_str: the string to interpret. Must conform to :rfc:2368.
    :return: the header fields and the body found in the mailto link
    """
    if mailto_str.startswith('mailto:'):
        import urllib.parse
        to_str, parms_str = mailto_str[7:].partition('?')[::2]
        headers: dict[str, list[str]] = {}
        body = ''

        to = urllib.parse.unquote(to_str)
        if to:
            headers['To'] = [to]

        for s in parms_str.split('&'):
            key, value = s.partition('=')[::2]
            key = key.capitalize()
            if key == 'Body':
                body = urllib.parse.unquote(value)
            elif value:
                headers[key] = [urllib.parse.unquote(value)]
        return (headers, body)
    else:
        return (None, None)


@functools.cache
def attachment_dir() -> str:
    """Return a private directory for copies of attachments handed to
    external programs. Programs such as xdg-open may return before the
    viewer has read its copy, so the directory is only removed when alot
    exits."""
    path = tempfile.mkdtemp(prefix='alot-')
    atexit.register(shutil.rmtree, path, ignore_errors=True)
    return path


def mailto_to_envelope(mailto_str: str) -> 'Envelope':
    """
    Interpret mailto-string into a :class:`alot.db.envelope.Envelope`
    """
    from alot.db.envelope import Envelope
    headers, body = parse_mailto(mailto_str)
    return Envelope(bodytext=body, headers=headers)


def get_xdg_env(env_name: str, fallback: str) -> str:
    """ Used for XDG_* env variables to return fallback if unset *or* empty """
    env = os.environ.get(env_name)
    return env if env else fallback


def get_notmuch_config_path() -> str:
    """ Find the notmuch config file via env vars and default locations """
    # This code is modeled after the description in nomtuch-config(1)
    # Case 1 is only applicable for the notmuch CLI
    # Case 2: the NOTMUCH_CONFIG env variable
    value = os.environ.get('NOTMUCH_CONFIG')
    if value is not None:
        return value
    # Case 3: new location in XDG config directory
    profile = os.environ.get('NOTMUCH_PROFILE', 'default')
    value = os.path.join(get_xdg_env('XDG_CONFIG_HOME',
                                     os.path.expanduser('~/.config')),
                         'notmuch', profile, 'config')
    if os.path.exists(value):
        return value
    # Case 4: traditional location in $HOME
    profile = os.environ.get('NOTMUCH_PROFILE', '')
    if profile:
        profile = '.' + profile
    return os.path.expanduser('~/.notmuch-config' + profile)
