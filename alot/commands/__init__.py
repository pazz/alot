# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse
import glob
import logging
import os
import re

from ..settings import settings
from ..helper import split_commandstring, string_decode


class Command(object):

    """base class for commands"""
    repeatable = False

    def __init__(self):
        self.prehook = None
        self.posthook = None
        self.undoable = False
        self.help = self.__doc__

    def apply(self, caller):
        """code that gets executed when this command is applied"""
        pass


class CommandCanceled(Exception):
    """ Exception triggered when an interactive command has been cancelled
    """
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
    """
    returns commandclass, argparser and forced parameters used to construct
    a command for `cmdname` when called in `mode`.

    :param cmdname: name of the command to look up
    :type cmdname: str
    :param mode: mode identifier
    :type mode: str
    :rtype: (:class:`Command`, :class:`~argparse.ArgumentParser`,
            dict(str->dict))

    >>> (cmd, parser, kwargs) = lookup_command('save', 'thread')
    >>> cmd
    <class 'alot.commands.thread.SaveAttachmentCommand'>
    """
    if cmdname in COMMANDS[mode]:
        return COMMANDS[mode][cmdname]
    elif cmdname in COMMANDS['global']:
        return COMMANDS['global'][cmdname]
    else:
        return None, None, None


def lookup_parser(cmdname, mode):
    """
    returns the :class:`CommandArgumentParser` used to construct a
    command for `cmdname` when called in `mode`.
    """
    return lookup_command(cmdname, mode)[1]


class CommandParseError(Exception):

    """could not parse commandline string"""
    pass


class CommandArgumentParser(argparse.ArgumentParser):

    """
    :class:`~argparse.ArgumentParser` that raises :class:`CommandParseError`
    instead of printing to `sys.stderr`"""
    def exit(self, message):
        raise CommandParseError(message)

    def error(self, message):
        raise CommandParseError(message)


class registerCommand(object):

    """
    Decorator used to register a :class:`Command` as
    handler for command `name` in `mode` so that it
    can be looked up later using :func:`lookup_command`.

    Consider this example that shows how a :class:`Command` class
    definition is decorated to register it as handler for
    'save' in mode 'thread' and add boolean and string arguments::

        @registerCommand('thread', 'save', arguments=[
            (['--all'], {'action': 'store_true', 'help':'save all'}),
            (['path'], {'nargs':'?', 'help':'path to save to'})],
            help='save attachment(s)')
        class SaveAttachmentCommand(Command):
            pass

    """
    def __init__(self, mode, name, help=None, usage=None,
                 forced=None, arguments=None):
        """
        :param mode: mode identifier
        :type mode: str
        :param name: command name to register as
        :type name: str
        :param help: help string summarizing what this command does
        :type help: str
        :param usage: overides the auto generated usage string
        :type usage: str
        :param forced: keyword parameter used for commands constructor
        :type forced: dict (str->str)
        :param arguments: list of arguments given as pairs (args, kwargs)
                          accepted by
                          :meth:`argparse.ArgumentParser.add_argument`.
        :type arguments: list of (list of str, dict (str->str)
        """
        self.mode = mode
        self.name = name
        self.help = help
        self.usage = usage
        self.forced = forced or {}
        self.arguments = arguments or []

    def __call__(self, klass):
        helpstring = self.help or klass.__doc__
        argparser = CommandArgumentParser(description=helpstring,
                                          usage=self.usage,
                                          prog=self.name, add_help=False)
        for args, kwargs in self.arguments:
            argparser.add_argument(*args, **kwargs)
        COMMANDS[self.mode][self.name] = (klass, argparser, self.forced)
        return klass


def commandfactory(cmdline, mode='global'):
    """
    parses `cmdline` and constructs a :class:`Command`.

    :param cmdline: command line to interpret
    :type cmdline: str
    :param mode: mode identifier
    :type mode: str

    >>> cmd = alot.commands.commandfactory('save --all /foo', mode='thread')
    >>> cmd
    <alot.commands.thread.SaveAttachmentCommand object at 0x272cf10
    >>> cmd.all
    True
    >>> cmd.path
    u'/foo'
    """
    # split commandname and parameters
    if not cmdline:
        return None
    logging.debug('mode:%s got commandline "%s"', mode, cmdline)
    # allow to shellescape without a space after '!'
    if cmdline.startswith('!'):
        cmdline = 'shellescape \'%s\'' % cmdline[1:]
    cmdline = re.sub(r'"(.*)"', r'"\\"\1\\""', cmdline)
    try:
        args = split_commandstring(cmdline)
    except ValueError as e:
        raise CommandParseError(e.message)
    args = map(lambda x: string_decode(x, 'utf-8'), args)
    logging.debug('ARGS: %s', args)
    cmdname = args[0]
    args = args[1:]

    # unfold aliases
    # TODO: read from settingsmanager

    # get class, argparser and forced parameter
    (cmdclass, parser, forcedparms) = lookup_command(cmdname, mode)
    if cmdclass is None:
        msg = 'unknown command: %s' % cmdname
        logging.debug(msg)
        raise CommandParseError(msg)

    parms = vars(parser.parse_args(args))
    parms.update(forcedparms)

    logging.debug('cmd parms %s', parms)

    # create Command
    cmd = cmdclass(**parms)

    # set pre and post command hooks
    get_hook = settings.get_hook
    cmd.prehook = get_hook('pre_%s_%s' % (mode, cmdname)) or \
        get_hook('pre_global_%s' % cmdname)
    cmd.posthook = get_hook('post_%s_%s' % (mode, cmdname)) or \
        get_hook('post_global_%s' % cmdname)

    return cmd


pyfiles = glob.glob1(os.path.dirname(__file__), '*.py')
__all__ = list(filename[:-3] for filename in pyfiles)
