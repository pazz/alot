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
    def __init__(self, mode, name, forced={}, arguments=[]):
        self.argparser = CommandArgumentParser(prog=name, add_help=False)
        for args,kwargs in arguments:
            self.argparser.add_argument(*args,**kwargs)
        self.mode = mode
        self.name = name
        self.forced = forced

    def __call__(self, klass):
        COMMANDS[self.mode][self.name] = (klass, self.argparser, self.forced)
        return klass

def commandfactory(cmdline, mode='global'):
    # split commandname and parameters
    if not cmdline:
        return None
    logging.debug('mode:%s got commandline "%s"' % (mode, cmdline))
    args = shlex.split(cmdline.encode('utf-8'))
    args = filter(lambda x: x.decode('utf-8'), args)
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
#    elif cmd == 'compose':
#        h = {}
#        if params:
#            h = {'To': params}
#        return commandfactory(cmd, mode=mode, headers=h)
#    elif cmd == 'retag':
#        return commandfactory(cmd, mode=mode, tagsstring=params)
#    elif cmd == 'shellescape':
#        return commandfactory(cmd, mode=mode, commandstring=params)
#    elif cmd == 'set':
#        key, value = params.split(' ', 1)
#        return commandfactory(cmd, mode=mode, key=key, value=value)
#    elif cmd == 'toggletag':
#        return commandfactory(cmd, mode=mode, tags=params.split())
#    elif cmd == 'fold':
#        return commandfactory(cmd, mode=mode, all=(params == '--all'))
#    elif cmd == 'unfold':
#        return commandfactory(cmd, mode=mode, all=(params == '--all'))
#    elif cmd == 'save':
#        args = params.split(' ')
#        allset = False
#        pathset = None
#        if args:
#            if args[0] == '--all':
#                allset = True
#                pathset = ' '.join(args[1:])
#            else:
#                pathset = params
#        return commandfactory(cmd, mode=mode, all=allset, path=pathset)
#    elif cmd == 'edit':
#        filepath = os.path.expanduser(params)
#        if os.path.isfile(filepath):
#            return commandfactory(cmd, mode=mode, path=filepath)
#    elif cmd == 'print':
#        args = [a.strip() for a in params.split()]
#        return commandfactory(cmd, mode=mode,
#                              whole_thread=('--thread' in args),
#                              separately=('--separately' in args))
#    elif cmd == 'pipeto':
#        return commandfactory(cmd, mode=mode, command=params)
#
#    elif not params and cmd in ['exit', 'flush', 'pyshell', 'taglist',
#                                'bclose', 'compose', 'openfocussed',
#                                'closefocussed', 'bnext', 'bprevious', 'retag',
#                                'refresh', 'bufferlist', 'refineprompt',
#                                'reply', 'open', 'groupreply', 'bounce',
#                                'openthread', 'toggleheaders', 'send',
#                                'cancel', 'reedit', 'select', 'retagprompt']:
#        return commandfactory(cmd, mode=mode)
#    else:
#        return None


__all__ = list(filename[:-3] for filename in glob.glob1(os.path.dirname(__file__), '*.py'))
