#!/usr/bin/python
"""
This file is part of alot, a terminal UI to notmuch mail (notmuchmail.org).
Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import argparse
import logging
import os

import settings
from db import DBManager
from ui import UI


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', dest='configfile',
                        default='~/.alot.rc',
                        help='config file')
    parser.add_argument('-C', dest='colours',
                        type=int,
                        choices=[1, 16, 88, 256],
                        help='colour mode')
    parser.add_argument('-r', dest='read_only',
                        action='store_true',
                        help='open db in read only mode')
    parser.add_argument('-p', dest='db_path',
                        help='path to notmuch index')
    parser.add_argument('-d', dest='debug_level',
                        default='info',
                        choices=['debug', 'info', 'warning', 'error'],
                        help='debug level')
    parser.add_argument('-l', dest='logfile',
                        default='debug.log',
                        help='logfile')
    parser.add_argument('query', nargs='?',
                        default='tag:inbox AND NOT tag:killed',
                        help='initial searchstring')
    return parser.parse_args()


def main():
    # interpret cml arguments
    args = parse_args()

    #read config file
    configfilename = os.path.expanduser(args.configfile)
    settings.setup(configfilename)

    # setup logging
    numeric_loglevel = getattr(logging, args.debug_level.upper(), None)
    logging.basicConfig(level=numeric_loglevel, filename=args.logfile)
    logger = logging.getLogger()

    # get ourselves a database manager
    dbman = DBManager(path=args.db_path, ro=args.read_only)
    # setup and start interface
    ui = UI(dbman,
            logger,
            args.query,
            args.colours,
    )

if __name__ == "__main__":
    main()
