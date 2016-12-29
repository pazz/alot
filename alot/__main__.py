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
from alot.commands import CommandParseError


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
    parser.add_argument('command', nargs=argparse.REMAINDER)
    options = parser.parse_args()
    if options.command:
        # We have a command after the initial options so we also parse that.
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='subcommand')
        search = subparsers.add_parser('search')
        search.add_argument('--sort', default='newest_first',
                            help='sort order',
                            choices=('oldest_first', 'newest_first',
                                     'message_id', 'unsorted'))
        search.add_argument('terms', nargs='+')
        compose = subparsers.add_parser('compose')
        compose.add_argument('--omit_signature', action='store_true',
                             help='do not add signature')
        compose.add_argument('--sender', help='From line')
        compose.add_argument('--subject', help='subject line')
        compose.add_argument('--to', help='recipients')
        compose.add_argument('--cc', help='copy to')
        compose.add_argument('--bcc', help='blind copy to')
        compose.add_argument('--template', type=argparse.FileType('r'),
                             help='path to template file')
        compose.add_argument('--attach', type=argparse.FileType('r'),
                             help='files to attach')

        command = parser.parse_args(options.command)
    else:
        command = None

    # logging
    root_logger = logging.getLogger()
    for log_handler in root_logger.handlers:
        root_logger.removeHandler(log_handler)
    root_logger = None
    numeric_loglevel = getattr(logging, options.debug_level.upper(), None)
    logfilename = os.path.expanduser(options.logfile)
    logformat = '%(levelname)s:%(module)s:%(message)s'
    logging.basicConfig(level=numeric_loglevel, filename=logfilename,
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
    notmuchpath = os.environ.get('NOTMUCH_CONFIG', '~/.notmuch-config')
    if options.notmuch_config:
        notmuchpath = options.notmuch_config
    notmuchconfig = os.path.expanduser(notmuchpath)

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
    try:
        if command is None:
            cmdstring = settings.get('initial_command')
        elif command.subcommand == 'search':
            query = ' '.join(command.terms)
            cmdstring = 'search --sort {} {}'.format(command.sort, query)
        elif command.subcommand == 'compose':
            cmdstring = ' '.join(options.command)
    except CommandParseError as err:
        sys.exit(err)

    # set up and start interface
    UI(dbman, cmdstring)

    # run the exit hook
    exit_hook = settings.get_hook('exit')
    if exit_hook is not None:
        exit_hook()

if __name__ == "__main__":
    main()
