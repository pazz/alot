import os
import re
import glob
import shlex
import logging
import argparse

import alot.settings
import alot.helper


class Command(object):
    """base class for commands"""
    def __init__(self, prehook=None, posthook=None):
        """
        :param prehook: name of the hook to call directly before
                        applying this command
        :type prehook: str
        :param posthook: name of the hook to call directly after
                         applying this command
        :type posthook: str
        """
        self.prehook = prehook
        self.posthook = posthook
        self.undoable = False
        self.help = self.__doc__

    def apply(self, caller):
        """code that gets executed when this command is applied"""
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

    >>> (cmd, parser, kwargs) = lookup_command('save', 'thread')
    >>> cmd
    <class 'alot.commands.thread.SaveAttachmentCommand'>
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
                 forced={}, arguments=[]):
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
        self.forced = forced
        self.arguments = arguments

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
    logging.debug('mode:%s got commandline "%s"' % (mode, cmdline))
    # allow to shellescape without a space after '!'
    if cmdline.startswith('!'):
        cmdline = 'shellescape \'%s\'' % cmdline[1:]
    cmdline = re.sub(r'"(.*)"', r'"\\"\1\\""', cmdline)
    try:
        args = shlex.split(cmdline.encode('utf-8'))
    except ValueError, e:
        raise CommandParseError(e.message)
    args = map(lambda x: alot.helper.string_decode(x, 'utf-8'), args)
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

    parms['prehook'] = alot.settings.config.get_hook('pre_' + cmdname)
    parms['posthook'] = alot.settings.config.get_hook('post_' + cmdname)

    logging.debug('cmd parms %s' % parms)
    return cmdclass(**parms)


pyfiles = glob.glob1(os.path.dirname(__file__), '*.py')
__all__ = list(filename[:-3] for filename in pyfiles)
