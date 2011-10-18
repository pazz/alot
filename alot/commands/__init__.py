import os
import sys
import re
import glob
import shlex
import logging
import argparse
import cStringIO

import alot.settings


class Command(object):
    """base class for commands"""
    def __init__(self, prehook=None, posthook=None):
        self.prehook = prehook
        self.posthook = posthook
        self.undoable = False
        self.help = self.__doc__

    def apply(self, caller):
        pass

    @classmethod
    def get_helpstring(cls):
        return cls.__doc__


COMMANDS = {
    'search': {},
    'envelope': {},
    'bufferlist': {},
    'taglist': {},
    'thread': {},
    'global': {},
}


def lookup_command(cmdname, mode):
    """returns commandclass, argparser and forcedparams
    for `cmdname` in `mode`"""
    if cmdname in COMMANDS[mode]:
        return COMMANDS[mode][cmdname]
    elif cmdname in COMMANDS['global']:
        return COMMANDS['global'][cmdname]
    else:
        return None, None, None


def lookup_parser(cmdname, mode):
    return lookup_command(cmdname, mode)[1]


class CommandParseError(Exception):
    pass


class CommandArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises `CommandParseError`
    instead of printing to sys.stderr"""
    def exit(self, message):
        raise CommandParseError(message)

    def error(self, message):
        raise CommandParseError(message)


class registerCommand(object):
    def __init__(self, mode, name, help=None, usage=None,
                 forced={}, arguments=[]):
        self.mode = mode
        self.name = name
        self.help = help
        self.usage = usage
        self.forced = forced
        self.arguments = arguments

    def __call__(self, klass):
        argparser = CommandArgumentParser(description=self.help,
                                          usage=self.usage,
                                          prog=self.name, add_help=False)
        for args, kwargs in self.arguments:
            argparser.add_argument(*args, **kwargs)
        COMMANDS[self.mode][self.name] = (klass, argparser, self.forced)
        return klass


def commandfactory(cmdline, mode='global'):
    # split commandname and parameters
    if not cmdline:
        return None
    logging.debug('mode:%s got commandline "%s"' % (mode, cmdline))
    # allow to shellescape without a space after '!'
    if cmdline.startswith('!'):
        cmdline = 'shellescape \'%s\'' % cmdline[1:]
    cmdline = re.sub(r'"(.*)"', r'"\\"\1\\""', cmdline)
    try:
        args = shlex.split(cmdline.encode('utf-8'))
    except ValueError, e:
        raise CommandParseError(e.message)
    args = map(lambda x: x.decode('utf-8'), args)  # get unicode strings
    logging.debug('ARGS: %s' % args)
    cmdname = args[0]
    args = args[1:]

    # unfold aliases
    if alot.settings.config.has_option('command-aliases', cmdname):
        cmdname = alot.settings.config.get('command-aliases', cmdname)

    # get class, argparser and forced parameter
    (cmdclass, parser, forcedparms) = lookup_command(cmdname, mode)
    if cmdclass is None:
        msg = 'unknown command: %s' % cmdname
        logging.debug(msg)
        raise CommandParseError(msg)

    parms = vars(parser.parse_args(args))
    parms.update(forcedparms)
    logging.debug('PARMS: %s' % parms)

    parms['prehook'] = alot.settings.hooks.get('pre_' + cmdname)
    parms['posthook'] = alot.settings.hooks.get('post_' + cmdname)

    logging.debug('cmd parms %s' % parms)
    return cmdclass(**parms)


#def interpret_commandline(cmdline, mode):

__all__ = list(filename[:-3] for filename in glob.glob1(os.path.dirname(__file__), '*.py'))
