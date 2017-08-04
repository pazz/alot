# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import argparse
import logging
import os
import sys

import alot
from alot.settings.const import settings
from alot.settings.errors import ConfigError
from alot.db.manager import DBManager
from alot.ui import UI
from alot.commands import *
from alot.commands import CommandParseError, COMMANDS
from alot.utils import argparse as cargparse


_SUBCOMMANDS = ['search', 'compose', 'bufferlist', 'taglist', 'pyshell']


def parser():
    """Parse command line arguments, validate them, and return them."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action='version',
                        version=alot.__version__)
    parser.add_argument('-r', '--read-only', action='store_true',
                        help='open db in read only mode')
    parser.add_argument('-c', '--config',
                        action=cargparse.ValidatedStoreAction,
                        validator=cargparse.require_file,
                        help='config file')
    parser.add_argument('-n', '--notmuch-config', default=os.environ.get(
                            'NOTMUCH_CONFIG',
                            os.path.expanduser('~/.notmuch-config')),
                        action=cargparse.ValidatedStoreAction,
                        validator=cargparse.require_file,
                        help='notmuch config')
    parser.add_argument('-C', '--colour-mode',
                        choices=(1, 16, 256), type=int, default=256,
                        help='terminal colour mode [default: %(default)s].')
    parser.add_argument('-p', '--mailindex-path',
                        action=cargparse.ValidatedStoreAction,
                        validator=cargparse.require_dir,
                        help='path to notmuch index')
    parser.add_argument('-d', '--debug-level', default='info',
                        choices=('debug', 'info', 'warning', 'error'),
                        help='debug log [default: %(default)s]')
    parser.add_argument('-l', '--logfile', default='/dev/null',
                        action=cargparse.ValidatedStoreAction,
                        validator=cargparse.optional_file_like,
                        help='logfile [default: %(default)s]')
    # We will handle the subcommands in a seperate run of argparse as argparse
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
        if os.path.exists(alotconfig):
            settings.alot_rc_path = alotconfig
    else:
        settings.alot_rc_path = options.config

    settings.notmuch_rc_path = options.notmuch_config

    try:
        settings.read_config()
        settings.read_notmuch_config()
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
