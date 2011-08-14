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
    args = shlex.split(command_line)
    try:
        output = subprocess.check_output(args)
    except subprocess.CalledProcessError:
        return None
    except OSError:
        return None
    return output
