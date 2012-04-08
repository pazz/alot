# coding=utf-8
from datetime import timedelta
from datetime import datetime
from collections import deque
from string import strip
import subprocess
import email
import os
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import urwid
import magic
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.defer import Deferred
import StringIO
import logging
import tempfile


def safely_get(clb, E, on_error=''):
    """
    returns result of :func:`clb` and falls back to `on_error`
    in case `E` is raised.

    :param clb: function to evaluate
    :type clb: callable
    :param E: exception to catch
    :type E: Exception
    :param on_error: default string returned when exception is caught
    :type on_error: str
    """
    try:
        return clb()
    except E:
        return on_error


def string_sanitize(string, tab_width=8):
    r"""
    strips, and replaces non-printable characters

    :param tab_width: number of spaces to replace tabs with. Read from
                      `globals.tabwidth` setting if `None`
    :type tab_width: int or `None`

    >>> string_sanitize(' foo\rbar ', 8)
    'foobar'
    >>> string_sanitize('foo\tbar', 8)
    'foo     bar'
    >>> string_sanitize('foo\t\tbar', 8)
    'foo             bar'
    """

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
    """safely decodes string to unicode bytestring,
    respecting `enc` as a hint"""

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


    >>> authors = u'King Kong, Mucho Muchacho, Jaime Huerta, Flash Gordon'
    >>> print shorten_author_string(authors, 60)
    King Kong, Mucho Muchacho, Jaime Huerta, Flash Gordon
    >>> print shorten_author_string(authors, 40)
    King, Mucho, Jaime, Flash
    >>> print shorten_author_string(authors, 20)
    King, …, Jai…, Flash
    >>> print shorten_author_string(authors, 10)
    King, …
    >>> print shorten_author_string(authors, 2)
    K…
    >>> print shorten_author_string(authors, 1)
    K
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
    ampm = d.strftime('%P')
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
            string = '%dmin ago' % (delta.seconds / 60)
        elif delta.seconds < 6 * 3600:
            string = '%dh ago' % (delta.seconds / 3600)
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

        This returns with the first screen content for interctive commands.

    :param cmdlist: shellcommand to call, already splitted into a list accepted
                    by :meth:`subprocess.Popen`
    :type cmdlist: list of str
    :param stdin: string to pipe to the process
    :type stdin: str
    :return: triple of stdout, error msg, return value of the shell command
    :rtype: str, str, int
    """

    out, err, ret = '', '', 0
    try:
        if stdin:
            proc = subprocess.Popen(cmdlist, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            out, err = proc.communicate(stdin)
            ret = proc.poll()
        else:
            out = subprocess.check_output(cmdlist)
            # todo: get error msg. rval
    except (subprocess.CalledProcessError, OSError), e:
        err = str(e)
        ret = -1

    out = string_decode(out, urwid.util.detected_encoding)
    err = string_decode(err, urwid.util.detected_encoding)
    return out, err, ret


def call_cmd_async(cmdlist, stdin=None, env=None):
    """
    get a shell commands output, error message and return value as a deferred.

    :type cmdlist: list of str
    :param stdin: string to pipe to the process
    :type stdin: str
    :return: deferred that calls back with triple of stdout, stderr and
             return value of the shell command
    :rtype: `twisted.internet.defer.Deferred`
    """

    class _EverythingGetter(ProcessProtocol):
        def __init__(self, deferred):
            self.deferred = deferred
            self.outBuf = StringIO.StringIO()
            self.errBuf = StringIO.StringIO()
            self.outReceived = self.outBuf.write
            self.errReceived = self.errBuf.write

        def processEnded(self, status):
            termenc = urwid.util.detected_encoding
            out = string_decode(self.outBuf.getvalue(), termenc)
            err = string_decode(self.errBuf.getvalue(), termenc)
            if status.value.exitCode == 0:
                self.deferred.callback(out)
            else:
                terminated_obj = status.value
                terminated_obj.stderr = err
                self.deferred.errback(terminated_obj)

    d = Deferred()
    environment = os.environ
    if env != None:
        environment.update(env)
    logging.debug('ENV = %s' % environment)
    logging.debug('CMD = %s' % cmdlist)
    proc = reactor.spawnProcess(_EverythingGetter(d), executable=cmdlist[0],
                                env=environment,
                                args=cmdlist)
    if stdin:
        logging.debug('writing to stdin')
        proc.write(stdin)
        proc.closeStdin()
    return d


def guess_mimetype(blob):
    """
    uses file magic to determine the mime-type of the given data blob.

    :param blob: file content as read by file.read()
    :type blob: data
    :returns: mime-type, falls back to 'application/octet-stream'
    :rtype: str
    """
    m = magic.open(magic.MAGIC_MIME_TYPE)
    m.load()
    return m.buffer(blob) or 'application/octet-stream'


def guess_encoding(blob):
    """
    uses file magic to determine the encoding of the given data blob.

    :param blob: file content as read by file.read()
    :type blob: data
    :returns: encoding
    :rtype: str
    """
    m = magic.open(magic.MAGIC_MIME_ENCODING)
    m.load()
    return m.buffer(blob)


# TODO: make this work on blobs, not paths
def mimewrap(path, filename=None, ctype=None):
    content = open(path, 'rb').read()
    ctype = ctype or guess_mimetype(content)
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
        return cmp(a.lower(), b.lower())


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
