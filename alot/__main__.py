# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import sys
import logging
import os

import alot
from alot.settings import settings
from alot.settings.errors import ConfigError
from alot.db.manager import DBManager
from alot.ui import UI
from alot.commands import *
from alot.commands import CommandParseError

from twisted.python import usage


class SubcommandOptions(usage.Options):
    optFlags = []

    def parseArgs(self, *args):
        self.args = args

    def as_argparse_opts(self):
        optstr = ''
        for k, v in self.items():
            # flags translate int value 0 or 1..
            if k in [a[0] for a in self.optFlags]:  # if flag
                optstr += ('--%s ' % k) * v
            else:
                if v is not None:
                    optstr += '--%s \'%s\' ' % (k, v)
        return optstr

    def opt_version(self):
        print alot.__version__
        sys.exit(0)


class ComposeOptions(SubcommandOptions):
    optParameters = [
        ['sender', '', None, 'From line'],
        ['subject', '', None, 'subject line'],
        ['to', [], None, 'recipients'],
        ['cc', '', None, 'copy to'],
        ['bcc', '', None, 'blind copy to'],
        ['template', '', None, 'path to template file'],
        ['attach', '', None, 'files to attach'],
    ]
    optFlags = [
        ['omit_signature', '', 'do not add signature'],
    ]

    def parseArgs(self, *args):
        SubcommandOptions.parseArgs(self, *args)
        self.rest = ' '.join(args) or None


class SearchOptions(SubcommandOptions):
    accepted = ['oldest_first', 'newest_first', 'message_id', 'unsorted']

    def colourint(val):
        if val not in accepted:
            raise ValueError("Unknown sort order")
        return val
    colourint.coerceDoc = "Must be one of " + str(accepted)
    optParameters = [
        ['sort', 'newest_first', None, 'Sort order'],
    ]


class Options(usage.Options):
    optFlags = [["read-only", "r", 'open db in read only mode'], ]

    def colourint(val):
        val = int(val)
        if val not in [1, 16, 256]:
            raise ValueError("Not in range")
        return val
    colourint.coerceDoc = "Must be 1, 16 or 256"

    def debuglogstring(val):
        if val not in ['error', 'debug', 'info', 'warning']:
            raise ValueError("Not in range")
        return val
    debuglogstring.coerceDoc = "Must be one of debug,info,warning or error"

    optParameters = [
        ['config', 'c', None, 'config file'],
        ['notmuch-config', 'n', None, 'notmuch config'],
        ['colour-mode', 'C', None, 'terminal colour mode', colourint],
        ['mailindex-path', 'p', None, 'path to notmuch index'],
        ['debug-level', 'd', 'info', 'debug log', debuglogstring],
        ['logfile', 'l', '/dev/null', 'logfile'],
    ]
    search_help = "start in a search buffer using the querystring provided "\
                  "as parameter. See the SEARCH SYNTAX section of notmuch(1)."

    subCommands = [['search', None, SearchOptions, search_help],
                   ['compose', None, ComposeOptions, "compose a new message"]]

    def opt_version(self):
        print alot.__version__
        sys.exit(0)


def main():
    # interpret cml arguments
    args = Options()
    try:
        args.parseOptions()  # When given no argument, parses sys.argv[1:]
    except usage.UsageError as errortext:
        print '%s' % errortext
        print 'Try --help for usage details.'
        sys.exit(1)

    # logging
    root_logger = logging.getLogger()
    for log_handler in root_logger.handlers:
        root_logger.removeHandler(log_handler)
    root_logger = None
    numeric_loglevel = getattr(logging, args['debug-level'].upper(), None)
    logfilename = os.path.expanduser(args['logfile'])
    logformat = '%(levelname)s:%(module)s:%(message)s'
    logging.basicConfig(level=numeric_loglevel, filename=logfilename,
                        filemode='w', format=logformat)

    # locate alot config files
    configfiles = [
        os.path.join(os.environ.get('XDG_CONFIG_HOME',
                                    os.path.expanduser('~/.config')),
                     'alot', 'config'),
    ]
    if args['config']:
        expanded_path = os.path.expanduser(args['config'])
        if not os.path.exists(expanded_path):
            msg = 'Config file "%s" does not exist. Goodbye for now.'
            sys.exit(msg % expanded_path)
        configfiles.insert(0, expanded_path)

    # locate notmuch config
    notmuchpath = os.environ.get('NOTMUCH_CONFIG', '~/.notmuch-config')
    if args['notmuch-config']:
        notmuchpath = args['notmuch-config']
    notmuchconfig = os.path.expanduser(notmuchpath)

    alotconfig = None
    # read the first alot config file we find
    for configfilename in configfiles:
        if os.path.exists(configfilename):
            alotconfig = configfilename
            break  # use only the first

    try:
        settings.read_config(alotconfig)
        settings.read_notmuch_config(notmuchconfig)
    except (ConfigError, OSError, IOError) as e:
        sys.exit(e)

    # store options given by config swiches to the settingsManager:
    if args['colour-mode']:
        settings.set('colourmode', args['colour-mode'])

    # get ourselves a database manager
    indexpath = settings.get_notmuch_setting('database', 'path')
    indexpath = args['mailindex-path'] or indexpath
    dbman = DBManager(path=indexpath, ro=args['read-only'])

    # determine what to do
    try:
        if args.subCommand == 'search':
            query = ' '.join(args.subOptions.args)
            cmdstring = 'search %s %s' % (args.subOptions.as_argparse_opts(),
                                          query)
        elif args.subCommand == 'compose':
            cmdstring = 'compose %s' % args.subOptions.as_argparse_opts()
            if args.subOptions.rest is not None:
                cmdstring += ' ' + args.subOptions.rest
        else:
            cmdstring = settings.get('initial_command')
    except CommandParseError as e:
        sys.exit(e)

    # set up and start interface
    UI(dbman, cmdstring)

    # run the exit hook
    exit_hook = settings.get_hook('exit')
    if exit_hook is not None:
        exit_hook()

if __name__ == "__main__":
    main()
