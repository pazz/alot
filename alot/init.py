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

from twisted.python import usage


class SearchOptions(usage.Options):
    def parseArgs(self, *args):
        self['query'] = ' '.join(args)


class ComposeOptions(usage.Options):
    optParameters = [
                ['sender', '', None, 'From line'],
                ['subject', '', None, 'subject line'],
                ['cc', '', None, 'copy to'],
                ['bcc', '', None, 'blind copy to'],
                ['template', '', None, 'path to template file'],
            ]

    def parseArgs(self, *args):
        self['to'] = ' '.join(args)

    def as_argparse_opts(self):
        optstr = ''
        for k, v in self.items():
            if v is not None:
                optstr += '--%s \'%s\' ' % (k, v)
        return optstr


class Options(usage.Options):
    optFlags = [
            ["read-only", "r", 'open db in read only mode'],
            ]

    def colourint(val):
        val = int(val)
        if val not in [1, 16, 256]:
            raise ValueError("Not in range")
        return val
    colourint.coerceDoc = "Must be 1, 16 or 256"
    optParameters = [
            ['config', 'c', '~/.config/alot/config', 'config file'],
            ['notmuch-config', 'n', '~/.notmuch-config', 'notmuch config'],
            ['colour-mode', 'C', 256, 'terminal colour mode', colourint],
            ['mailindex-path', 'p', None, 'path to notmuch index'],
            ['debug-level', 'd', 'info', 'debug level used with -l'],
            ['logfile', 'l', '/dev/null', 'logfile'],
            ]
    subCommands = [['search', None, SearchOptions, "search for threads"],
                   ['compose', None, ComposeOptions, "compose a message"]]

    def opt_version(self):
        print alot.__version__
        sys.exit(0)


def main():
    # interpret cml arguments
    args = Options()
    try:
        args.parseOptions()  # When given no argument, parses sys.argv[1:]
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    # locate alot config files
    configfiles = [
        os.path.join(os.environ.get('XDG_CONFIG_HOME',
                                    os.path.expanduser('~/.config')),
                     'alot', 'config'),
        os.path.expanduser('~/.alot.rc'),
    ]
    if args['config']:
        expanded_path = os.path.expanduser(args['config'])
        if not os.path.exists(expanded_path):
            sys.exit('File %s does not exist' % expanded_path)
        configfiles.insert(0, expanded_path)

    # locate notmuch config
    notmuchfile = os.path.expanduser(args['notmuch-config'])

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
    numeric_loglevel = getattr(logging, args['debug-level'].upper(), None)
    logfilename = os.path.expanduser(args['logfile'])
    logging.basicConfig(level=numeric_loglevel, filename=logfilename)
    logger = logging.getLogger()

    #logger.debug(commands.COMMANDS)
    #accountman
    aman = AccountManager(settings.config)

    # get ourselves a database manager
    dbman = DBManager(path=args['mailindex-path'], ro=args['read-only'])

    # get initial searchstring
    try:
        if args.subCommand == 'search':
            query = args.subOptions['query']
            cmd = commands.commandfactory('search ' + query, 'global')
        elif args.subCommand == 'compose':
            cmdstring = 'compose %s' % args.subOptions.as_argparse_opts()
            print cmdstring
            cmd = commands.commandfactory(cmdstring, 'global')
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
       args['colour-mode'],
    )

if __name__ == "__main__":
    main()
