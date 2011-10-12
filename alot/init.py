#!/usr/bin/env python
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
import sys
import argparse
import logging
import os

import settings
from account import AccountManager
from db import DBManager
from ui import UI
import command
from Commands import *


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', dest='configfile',
                        default=None,
                        help='alot\'s config file')
    parser.add_argument('-n', dest='notmuchconfigfile',
                        default='~/.notmuch-config',
                        help='notmuch\'s config file')
    parser.add_argument('-C', dest='colours',
                        type=int,
                        choices=[1, 16, 256],
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
                        default='/dev/null',
                        help='logfile')
    parser.add_argument('command', nargs='?',
                        default='',
                        help='initial command')
    return parser.parse_args()


def main():
    # interpret cml arguments
    args = parse_args()

    # locate and read config file
    configfiles = [
        os.path.join(os.environ.get('XDG_CONFIG_HOME',
                                    os.path.expanduser('~/.config')),
                     'alot', 'config'),
        os.path.expanduser('~/.alot.rc'),
    ]
    if args.configfile:
        expanded_path = os.path.expanduser(args.configfile)
        if not os.path.exists(expanded_path):
            sys.exit('File %s does not exist' % expanded_path)
        configfiles.insert(0, expanded_path)

    for configfilename in configfiles:
        if os.path.exists(configfilename):
            settings.config.read(configfilename)
            break  # use only the first

    # read notmuch config
    notmuchfile = os.path.expanduser(args.notmuchconfigfile)
    settings.notmuchconfig.read(notmuchfile)
    settings.hooks.setup(settings.config.get('general', 'hooksfile'))

    # setup logging
    numeric_loglevel = getattr(logging, args.debug_level.upper(), None)
    logfilename = os.path.expanduser(args.logfile)
    logging.basicConfig(level=numeric_loglevel, filename=logfilename)
    logger = logging.getLogger()

    logger.debug(command.COMMANDS)
    #accountman
    aman = AccountManager(settings.config)

    # get ourselves a database manager
    dbman = DBManager(path=args.db_path, ro=args.read_only)

    # get initial searchstring
    if args.command != '':
        cmd = command.interpret_commandline(args.command, 'global')
        if cmd is None:
            sys.exit('Invalid command: ' + args.command)
    else:
        default_commandline = settings.config.get('general', 'initial_command')
        cmd = command.interpret_commandline(default_commandline, 'global')

    # set up and start interface
    UI(dbman,
       logger,
       aman,
       cmd,
       args.colours,
    )

if __name__ == "__main__":
    main()
