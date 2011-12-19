#!/usr/bin/env python
import sys
import argparse
import logging
import os

import settings
import ConfigParser
from account import AccountManager
from db import DBManager
from ui import UI
import alot.commands as commands
from commands import *
from alot.commands import CommandParseError
import alot


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
    parser.add_argument('-v', '--version', action='version',
                        version='%(prog)s ' + alot.__version__)
    return parser.parse_args()


def main():
    # interpret cml arguments
    args = parse_args()

    # locate alot config files
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

    # locate notmuch config
    notmuchfile = os.path.expanduser(args.notmuchconfigfile)

    try:
        # read the first alot config file we find
        for configfilename in configfiles:
            if os.path.exists(configfilename):
                settings.config.read(configfilename)
                break  # use only the first

        # read notmuch config
        settings.notmuchconfig.read(notmuchfile)

    except ConfigParser.Error, e:  # exit on parse errors
        sys.exit(e)

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
    try:
        if args.command != '':
            cmd = commands.commandfactory(args.command, 'global')
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
