import os
import sys
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
    def __init__(self, mode, name, help=None, forced={}, arguments=[]):
        self.mode = mode
        self.name = name
        self.help = help
        self.forced = forced
        self.arguments = arguments

    def __call__(self, klass):
        argparser = CommandArgumentParser(description=self.help,
                                          prog=self.name, add_help=False)
        for args,kwargs in self.arguments:
            argparser.add_argument(*args, **kwargs)
        COMMANDS[self.mode][self.name] = (klass, argparser, self.forced)
        return klass

def commandfactory(cmdline, mode='global'):
    # split commandname and parameters
    if not cmdline:
        return None
    logging.debug('mode:%s got commandline "%s"' % (mode, cmdline))
    args = shlex.split(cmdline.encode('utf-8'))
    args = map(lambda x: x.decode('utf-8'), args)  # get unicode strings
    logging.debug('ARGS: %s' % args)
    cmdname = args[0]
    args = args[1:]

    # unfold aliases
    if alot.settings.config.has_option('command-aliases', cmdname):
        cmdname = alot.settings.config.get('command-aliases', cmdname)

    # allow to shellescape without a space after '!'
    if cmdname.startswith('!'):
        argstring = cmdname[1:] + ' ' + argstring
        cmdname = 'shellescape'

    # get class, argparser and forced parameter
    (cmdclass, parser, forcedparms) = lookup_command(cmdname,mode)
    if cmdclass is None:
        msg = 'unknown command: %s' % cmdname
        logging.debug(msg)
        raise CommandParseError(msg)

    #logging.debug(parser)
    parms = vars(parser.parse_args(args))
    logging.debug('PARMS: %s' % parms)
    logging.debug(parms)

    parms.update(forcedparms)
    # still needed?
    #for (key, value) in kwargs.items():
    #    if callable(value):
    #        parms[key] = value()
    #    else:
    #        parms[key] = value

    parms['prehook'] = alot.settings.hooks.get('pre_' + cmdname)
    parms['posthook'] = alot.settings.hooks.get('post_' + cmdname)

    logging.debug('cmd parms %s' % parms)
    return cmdclass(**parms)


#def interpret_commandline(cmdline, mode):
#
#    elif cmd == 'shellescape':
#        return commandfactory(cmd, mode=mode, commandstring=params)
#    elif cmd == 'edit':
#        filepath = os.path.expanduser(params)
#        if os.path.isfile(filepath):
#            return commandfactory(cmd, mode=mode, path=filepath)

__all__ = list(filename[:-3] for filename in glob.glob1(os.path.dirname(__file__), '*.py'))
