# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse
import locale
import logging
import os
import sys

import alot
from alot.settings.const import settings
from alot.settings.errors import ConfigError
from alot.helper import get_xdg_env, get_notmuch_config_path
from alot.db.manager import DBManager
from alot.ui import UI
from alot.commands import *
from alot.commands import CommandParseError, COMMANDS
from alot.utils import argparse as cargparse

from twisted.internet import asyncioreactor
asyncioreactor.install()


_SUBCOMMANDS = ['search', 'compose', 'bufferlist', 'taglist', 'namedqueries',
                'pyshell']


def parser():
    """Parse command line arguments, validate them, and return them."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-r', '--read-only', action='store_true',
                        help='open notmuch database in read-only mode')
    parser.add_argument('-c', '--config', metavar='FILENAME',
                        action=cargparse.ValidatedStoreAction,
                        validator=cargparse.require_file,
                        help='configuration file')
    parser.add_argument('-n', '--notmuch-config', metavar='FILENAME',
                        default=get_notmuch_config_path(),
                        action=cargparse.ValidatedStoreAction,
                        validator=cargparse.require_file,
                        help='notmuch configuration file')
    parser.add_argument('-C', '--colour-mode', metavar='COLOURS',
                        choices=(1, 16, 256), type=int,
                        help='number of colours to use')
    parser.add_argument('-p', '--mailindex-path', metavar='PATH',
                        action=cargparse.ValidatedStoreAction,
                        validator=cargparse.require_dir,
                        help='path to notmuch index')
    parser.add_argument('-d', '--debug-level', metavar='LEVEL', default='info',
                        choices=('debug', 'info', 'warning', 'error'),
                        help='debug level [default: %(default)s]')
    parser.add_argument('-l', '--logfile', metavar='FILENAME',
                        default='/dev/null',
                        action=cargparse.ValidatedStoreAction,
                        validator=cargparse.optional_file_like,
                        help='log file [default: %(default)s]')
    parser.add_argument('-h', '--help', action='help',
                        help='display this help and exit')
    parser.add_argument('-v', '--version', action='version',
                        version=alot.__version__,
                        help='output version information and exit')
    # We will handle the subcommands in a separate run of argparse as argparse
    # does not support optional subcommands until now.
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help='possible subcommands are {}'.format(
                            ', '.join(_SUBCOMMANDS)))
    options = parser.parse_args()

    if options.command:
        # We have a command after the initial options so we also parse that.
        # But we just use the parser that is already defined for the internal
        # command that will back this subcommand.
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='subcommand')
        for subcommand in _SUBCOMMANDS:
            subparsers.add_parser(subcommand,
                                  parents=[COMMANDS['global'][subcommand][1]])
        command = parser.parse_args(options.command)
    else:
        command = None

    return options, command


def main():
    """The main entry point to alot.  It parses the command line and prepares
    for the user interface main loop to run."""
    options, command = parser()

    # locale
    locale.setlocale(locale.LC_ALL, '')

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
    cpath = options.config
    if options.config is None:
        xdg_dir = get_xdg_env('XDG_CONFIG_HOME',
                              os.path.expanduser('~/.config'))
        alotconfig = os.path.join(xdg_dir, 'alot', 'config')
        if os.path.exists(alotconfig):
            cpath = alotconfig

    try:
        settings.read_config(cpath)
        settings.read_notmuch_config(options.notmuch_config)
    except (ConfigError, OSError, IOError) as e:
        print('Error when parsing a config file. '
              'See log for potential details.')
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
    elif command.subcommand in _SUBCOMMANDS:
        cmdstring = ' '.join(options.command)

    # set up and start interface
    UI(dbman, cmdstring)

    # run the exit hook
    exit_hook = settings.get_hook('exit')
    if exit_hook is not None:
        exit_hook()


if __name__ == "__main__":
    main()
