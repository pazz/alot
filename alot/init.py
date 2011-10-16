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
import alot.commands as commands
from commands import *
from alot.commands import CommandParseError
import alot.args


def main():
    # interpret cml arguments
    args = alot.args.globalparser.parse_args()

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

    #logger.debug(commands.COMMANDS)
    #accountman
    aman = AccountManager(settings.config)

    # get ourselves a database manager
    dbman = DBManager(path=args.db_path, ro=args.read_only)

    # get initial searchstring
    logger.debug(args)
    try:
        if args.command != '':
            parms = vars(args)
            logger.debug(parms)
            cmdclass = commands.interpret_commandline(args.command, 'global')[0]
            cmd = cmdclass(**parms)
        else:
            default_commandline = settings.config.get('general',
                                                      'initial_command')
            cmd = commands.commandfactory(default_commandline, 'global')
    except CommandParseError, e:
        sys.exit(e)

    # set up and start interface
    UI(dbman,
       logger,
       aman,
       cmd,
       args.colours,
    )

if __name__ == "__main__":
    main()
