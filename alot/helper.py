# -*- coding: utf-8 -*-
# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2017-2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from datetime import timedelta
from datetime import datetime
from collections import deque
import logging
import mimetypes
import os
import re
import shlex
import subprocess
import email
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import asyncio

import urwid
import magic


def split_commandline(s, comments=False, posix=True):
    """
    splits semi-colon separated commandlines
    """
    # shlex seems to remove unescaped quotes and backslashes
    s = s.replace('\\', '\\\\')
    s = s.replace('\'', '\\\'')
    s = s.replace('\"', '\\\"')
    lex = shlex.shlex(s, posix=posix)
    lex.whitespace_split = True
    lex.whitespace = ';'
    if not comments:
        lex.commenters = ''
    return list(lex)


def split_commandstring(cmdstring):
    """
    split command string into a list of strings to pass on to subprocess.Popen
    and the like. This simply calls shlex.split but works also with unicode
    bytestrings.
    """
    assert isinstance(cmdstring, str)
    return shlex.split(cmdstring)


def string_sanitize(string, tab_width=8):
    r"""
    strips, and replaces non-printable characters

    :param tab_width: number of spaces to replace tabs with. Read from
                      `globals.tabwidth` setting if `None`
    :type tab_width: int or `None`

    >>> string_sanitize(' foo\rbar ', 8)
    ' foobar '
    >>> string_sanitize('foo\tbar', 8)
    'foo     bar'
    >>> string_sanitize('foo\t\tbar', 8)
    'foo             bar'
    """

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
    """
    safely decodes string to unicode bytestring, respecting `enc` as a hint.

    :param string: the string to decode
    :type string: str or unicode
    :param enc: a hint what encoding is used in string ('ascii', 'utf-8', ...)
    :type enc: str
    :returns: the unicode decoded input string
    :rtype: unicode

    """

    if enc is None:
        enc = 'ascii'
    try:
        string = str(string, enc, errors='replace')
    except LookupError:  # malformed enc string
        string = string.decode('ascii', errors='replace')
    except TypeError:  # already str
        pass
    return string


def shorten(string, maxlen):
    """shortens string if longer than maxlen, appending ellipsis"""
    if 1 < maxlen < len(string):
        string = string[:maxlen - 1] + u'…'
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

      - If possible, last author is also shown (if too long, uses ellipsis)

      - If there are more than 2 authors in the thread, show the
        maximum of them. More recent senders have higher priority.

      - If it is finally necessary to hide any author, an ellipsis
        between first and next authors is added.
    """

    # I will create a list of authors by parsing author_string. I use
    # deque to do popleft without performance penalties
    authors = deque()

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
    authors_chain = deque()

    if len(authors) == 0:
        return u''

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
    """
    translates :class:`datetime` `d` to a "sup-style" human readable string.

    >>> now = datetime.now()
    >>> now.strftime('%c')
    'Sat 31 Mar 2012 14:47:26 '
    >>> pretty_datetime(now)
    u'just now'
    >>> pretty_datetime(now - timedelta(minutes=1))
    u'1min ago'
    >>> pretty_datetime(now - timedelta(hours=5))
    u'5h ago'
    >>> pretty_datetime(now - timedelta(hours=12))
    u'02:54am'
    >>> pretty_datetime(now - timedelta(days=1))
    u'yest 02pm'
    >>> pretty_datetime(now - timedelta(days=2))
    u'Thu 02pm'
    >>> pretty_datetime(now - timedelta(days=7))
    u'Mar 24'
    >>> pretty_datetime(now - timedelta(days=356))
    u'Apr 2011'
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
    return string_decode(string, 'UTF-8')


def call_cmd(cmdlist, stdin=None):
    """
    get a shell commands output, error message and return value and immediately
    return.

    .. warning::

        This returns with the first screen content for interactive commands.

    :param cmdlist: shellcommand to call, already splitted into a list accepted
                    by :meth:`subprocess.Popen`
    :type cmdlist: list of str
    :param stdin: string to pipe to the process
    :type stdin: str, bytes, or None
    :return: triple of stdout, stderr, return value of the shell command
    :rtype: str, str, int
    """
    termenc = urwid.util.detected_encoding
    if isinstance(stdin, str):
        stdin = stdin.encode(termenc)
    try:

        logging.debug("Calling %s" % cmdlist)
        proc = subprocess.Popen(
            cmdlist,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if stdin is not None else None)
    except OSError as e:
        out = b''
        err = e.strerror
        ret = e.errno
    else:
        out, err = proc.communicate(stdin)
        ret = proc.returncode

    out = string_decode(out, termenc)
    err = string_decode(err, termenc)
    return out, err, ret


async def call_cmd_async(cmdlist, stdin=None, env=None):
    """Given a command, call that command asynchronously and return the output.

    This function only handles `OSError` when creating the subprocess, any
    other exceptions raised either durring subprocess creation or while
    exchanging data with the subprocess are the caller's responsibility to
    handle.

    If such an `OSError` is caught, then returncode will be set to 1, and the
    error value will be set to the str() method fo the exception.

    :type cmdlist: list of str
    :param stdin: string to pipe to the process
    :type stdin: str
    :return: Tuple of stdout, stderr, returncode
    :rtype: tuple[str, str, int]
    """
    termenc = urwid.util.detected_encoding
    cmdlist = [s.encode(termenc) for s in cmdlist]

    environment = os.environ.copy()
    if env is not None:
        environment.update(env)
    logging.debug('ENV = %s', environment)
    logging.debug('CMD = %s', cmdlist)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmdlist,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if stdin else None)
    except OSError as e:
        return ('', str(e), 1)
    out, err = await proc.communicate(stdin.encode(termenc) if stdin else None)
    return (out.decode(termenc), err.decode(termenc), proc.returncode)


def guess_mimetype(blob):
    """
    uses file magic to determine the mime-type of the given data blob.

    :param blob: file content as read by file.read()
    :type blob: data
    :returns: mime-type, falls back to 'application/octet-stream'
    :rtype: str
    """
    mimetype = 'application/octet-stream'
    # this is a bit of a hack to support different versions of python magic.
    # Hopefully at some point this will no longer be necessary
    #
    # the version with open() is the bindings shipped with the file source from
    # http://darwinsys.com/file/ - this is what is used by the python-magic
    # package on Debian/Ubuntu. However, it is not available on pypi/via pip.
    #
    # the version with from_buffer() is available at
    # https://github.com/ahupp/python-magic and directly installable via pip.
    #
    # for more detail see https://github.com/pazz/alot/pull/588
    if hasattr(magic, 'open'):
        m = magic.open(magic.MAGIC_MIME_TYPE)
        m.load()
        magictype = m.buffer(blob)
    elif hasattr(magic, 'from_buffer'):
        # cf. issue #841
        magictype = magic.from_buffer(blob, mime=True) or magictype
    else:
        raise Exception('Unknown magic API')

    # libmagic does not always return proper mimetype strings, cf. issue #459
    if re.match(r'\w+\/\w+', magictype):
        mimetype = magictype
    return mimetype


def guess_encoding(blob):
    """
    uses file magic to determine the encoding of the given data blob.

    :param blob: file content as read by file.read()
    :type blob: data
    :returns: encoding
    :rtype: str
    """
    # this is a bit of a hack to support different versions of python magic.
    # Hopefully at some point this will no longer be necessary
    #
    # the version with open() is the bindings shipped with the file source from
    # http://darwinsys.com/file/ - this is what is used by the python-magic
    # package on Debian/Ubuntu.  However it is not available on pypi/via pip.
    #
    # the version with from_buffer() is available at
    # https://github.com/ahupp/python-magic and directly installable via pip.
    #
    # for more detail see https://github.com/pazz/alot/pull/588
    if hasattr(magic, 'open'):
        m = magic.open(magic.MAGIC_MIME_ENCODING)
        m.load()
        return m.buffer(blob)
    elif hasattr(magic, 'from_buffer'):
        m = magic.Magic(mime_encoding=True)
        return m.from_buffer(blob)
    else:
        raise Exception('Unknown magic API')


def try_decode(blob):
    """Guess the encoding of blob and try to decode it into a str.

    :param bytes blob: The bytes to decode
    :returns: the decoded blob
    :rtype: str
    """
    assert isinstance(blob, bytes), 'cannot decode a str or non-bytes object'
    return blob.decode(guess_encoding(blob))


def libmagic_version_at_least(version):
    """
    checks if the libmagic library installed is more recent than a given
    version.

    :param version: minimum version expected in the form XYY (i.e. 5.14 -> 514)
                    with XYY >= 513
    """
    if hasattr(magic, 'open'):
        magic_wrapper = magic._libraries['magic']
    elif hasattr(magic, 'from_buffer'):
        magic_wrapper = magic.libmagic
    else:
        raise Exception('Unknown magic API')

    if not hasattr(magic_wrapper, 'magic_version'):
        # The magic_version function has been introduced in libmagic 5.13,
        # if it's not present, we can't guess right, so let's assume False
        return False

    # Depending on the libmagic/ctypes version, magic_version is a function or
    # a callable:
    if callable(magic_wrapper.magic_version):
        return magic_wrapper.magic_version() >= version

    return magic_wrapper.magic_version >= version


# TODO: make this work on blobs, not paths
def mimewrap(path, filename=None, ctype=None):
    """Take the contents of the given path and wrap them into an email MIME
    part according to the content type.  The content type is auto detected from
    the actual file contents and the file name if it is not given.

    :param path: the path to the file contents
    :type path: str
    :param filename: the file name to use in the generated MIME part
    :type filename: str or None
    :param ctype: the content type of the file contents in path
    :type ctype: str or None
    :returns: the message MIME part storing the data from path
    :rtype: subclasses of email.mime.base.MIMEBase
    """

    with open(path, 'rb') as f:
        content = f.read()
    if not ctype:
        ctype = guess_mimetype(content)
        # libmagic < 5.12 incorrectly detects excel/powerpoint files as
        # 'application/msword' (see #179 and #186 in libmagic bugtracker)
        # This is a workaround, based on file extension, useful as long
        # as distributions still ship libmagic 5.11.
        if (ctype == 'application/msword' and
                not libmagic_version_at_least(513)):
            mimetype, _ = mimetypes.guess_type(path)
            if mimetype:
                ctype = mimetype

    maintype, subtype = ctype.split('/', 1)
    if maintype == 'text':
        part = MIMEText(content.decode(guess_encoding(content), 'replace'),
                        _subtype=subtype,
                        _charset='utf-8')
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


def shell_quote(text):
    """Escape the given text for passing it to the shell for interpretation.
    The resulting string will be parsed into one "word" (in the sense used in
    the shell documentation, see sh(1)) by the shell.

    :param text: the text to quote
    :type text: str
    :returns: the quoted text
    :rtype: str
    """
    return "'%s'" % text.replace("'", """'"'"'""")


def humanize_size(size):
    """Create a nice human readable representation of the given number
    (understood as bytes) using the "KiB" and "MiB" suffixes to indicate
    kibibytes and mebibytes. A kibibyte is defined as 1024 bytes (as opposed to
    a kilobyte which is 1000 bytes) and a mibibyte is 1024**2 bytes (as opposed
    to a megabyte which is 1000**2 bytes).

    :param size: the number to convert
    :type size: int
    :returns: the human readable representation of size
    :rtype: str
    """
    for factor, format_string in ((1, '%i'),
                                  (1024, '%iKiB'),
                                  (1024 * 1024, '%.1fMiB')):
        if size / factor < 1024:
            return format_string % (size / factor)
    return format_string % (size / factor)


def parse_mailcap_nametemplate(tmplate='%s'):
    """this returns a prefix and suffix to be used
    in the tempfile module for a given mailcap nametemplate string"""
    nt_list = tmplate.split('%s')
    template_prefix = ''
    template_suffix = ''
    if len(nt_list) == 2:
        template_suffix = nt_list[1]
        template_prefix = nt_list[0]
    else:
        template_suffix = tmplate
    return (template_prefix, template_suffix)


def parse_mailto(mailto_str):
    """
    Interpret mailto-string

    :param mailto_str: the string to interpret. Must conform to :rfc:2368.
    :type mailto_str: str
    :return: the header fields and the body found in the mailto link as a tuple
        of length two
    :rtype: tuple(dict(str->list(str)), str)
    """
    if mailto_str.startswith('mailto:'):
        import urllib.parse
        to_str, parms_str = mailto_str[7:].partition('?')[::2]
        headers = {}
        body = u''

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


def mailto_to_envelope(mailto_str):
    """
    Interpret mailto-string into a :class:`alot.db.envelope.Envelope`
    """
    from alot.db.envelope import Envelope
    headers, body = parse_mailto(mailto_str)
    return Envelope(bodytext=body, headers=headers)


def RFC3156_canonicalize(text):
    """
    Canonicalizes plain text (MIME-encoded usually) according to RFC3156.

    This function works as follows (in that order):

    1. Convert all line endings to \\\\r\\\\n (DOS line endings).
    2. Encode all occurrences of "From " at the beginning of a line
       to "From=20" in order to prevent other mail programs to replace
       this with "> From" (to avoid MBox conflicts) and thus invalidate
       the signature.

    :param text: text to canonicalize (already encoded as quoted-printable)
    :rtype: str
    """
    text = re.sub("\r?\n", "\r\n", text)
    text = re.sub("^From ", "From=20", text, flags=re.MULTILINE)
    return text


def get_xdg_env(env_name, fallback):
    """ Used for XDG_* env variables to return fallback if unset *or* empty """
    env = os.environ.get(env_name)
    return env if env else fallback
