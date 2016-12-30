# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse
import logging
import os
import sys

import alot
from alot.settings import settings
from alot.settings.errors import ConfigError
from alot.db.manager import DBManager
from alot.ui import UI
from alot.commands import *
from alot.commands import CommandParseError, COMMANDS


def main():
    # set up the parser to parse the command line options.
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action='version',
                        version=alot.__version__)
    parser.add_argument('-r', '--read-only', action='store_true',
                        help='open db in read only mode')
    parser.add_argument('-c', '--config', type=argparse.FileType('r'),
                        help='config file')
    parser.add_argument('-n', '--notmuch-config', type=argparse.FileType('r'),
                        help='notmuch config')
    parser.add_argument('-C', '--colour-mode',
                        choices=(1, 16, 256), type=int, default=256,
                        help='terminal colour mode [default: %(default)s].')
    parser.add_argument('-p', '--mailindex-path', #type=directory,
                        help='path to notmuch index')
    parser.add_argument('-d', '--debug-level', default='info',
                        choices=('debug', 'info', 'warning', 'error'),
                        help='debug log [default: %(default)s]')
    parser.add_argument('-l', '--logfile', default='/dev/null',
                        type=lambda x: argparse.FileType('w')(x).name,
                        help='logfile [default: %(default)s]')
    # We will handle the subcommands in a seperate run of argparse as argparse
    # does not support optional subcommands until now.
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help="possible subcommands are 'search' and 'compose'")
    options = parser.parse_args()
    if options.command:
        # We have a command after the initial options so we also parse that.
        # But we just use the parser that is already defined for the internal
        # command that will back this subcommand.
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='subcommand')
        subparsers.add_parser('search',
                              parents=[COMMANDS['global']['search'][1]])
        subparsers.add_parser('compose',
                              parents=[COMMANDS['global']['compose'][1]])
        command = parser.parse_args(options.command)
    else:
        command = None

    # logging
    root_logger = logging.getLogger()
    for log_handler in root_logger.handlers:
        root_logger.removeHandler(log_handler)
    root_logger = None
    numeric_loglevel = getattr(logging, options.debug_level.upper(), None)
    logformat = '%(levelname)s:%(module)s:%(message)s'
    logging.basicConfig(level=numeric_loglevel, filename=options.logfile,
                        filemode='w', format=logformat)

    # locate alot config files
    if options.config is None:
        alotconfig = os.path.join(
            os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
            'alot', 'config')
        if not os.path.exists(alotconfig):
            alotconfig = None
    else:
        alotconfig = options.config

    # locate notmuch config
    if options.notmuch_config:
        notmuchconfig = options.notmuch_config
    else:
        notmuchconfig = os.environ.get('NOTMUCH_CONFIG',
                                       os.path.expanduser('~/.notmuch-config'))

    try:
        settings.read_config(alotconfig)
        settings.read_notmuch_config(notmuchconfig)
    except (ConfigError, OSError, IOError) as e:
        sys.exit(e)

    # store options given by config swiches to the settingsManager:
    if options.colour_mode:
        settings.set('colourmode', options.colour_mode)

    # get ourselves a database manager
    indexpath = settings.get_notmuch_setting('database', 'path')
    indexpath = options.mailindex_path or indexpath
    dbman = DBManager(path=indexpath, ro=options.read_only)

    # determine what to do
    if command is None:
        try:
            cmdstring = settings.get('initial_command')
        except CommandParseError as err:
            sys.exit(err)
    elif command.subcommand in ('compose', 'search'):
        cmdstring = ' '.join(options.command)

    # set up and start interface
    UI(dbman, cmdstring)

    # run the exit hook
    exit_hook = settings.get_hook('exit')
    if exit_hook is not None:
        exit_hook()


if __name__ == "__main__":
    main()
