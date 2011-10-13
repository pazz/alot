import os
import glob
import logging

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


class registerCommand(object):
    def __init__(self, mode, name, defaultparms):
        self.mode = mode
        self.name = name
        self.defaultparms = defaultparms

    def __call__(self, klass):
        COMMANDS[self.mode][self.name] = (klass, self.defaultparms)
        return klass


def register(klass):
    COMMANDS['classes'] = klass
    return klass


def commandfactory(cmdname, mode='global', **kwargs):
    if cmdname in COMMANDS[mode]:
        (cmdclass, parms) = COMMANDS[mode][cmdname]
    elif cmdname in COMMANDS['global']:
        (cmdclass, parms) = COMMANDS['global'][cmdname]
    else:
        logging.error('there is no command %s' % cmdname)
    parms = parms.copy()
    parms.update(kwargs)
    for (key, value) in kwargs.items():
        if callable(value):
            parms[key] = value()
        else:
            parms[key] = value

    parms['prehook'] = alot.settings.hooks.get('pre_' + cmdname)
    parms['posthook'] = alot.settings.hooks.get('post_' + cmdname)

    logging.debug('cmd parms %s' % parms)
    return cmdclass(**parms)


def interpret_commandline(cmdline, mode):
    # TODO: use argparser here!
    if not cmdline:
        return None
    logging.debug('mode:%s got commandline "%s"' % (mode, cmdline))
    args = cmdline.split(' ', 1)
    cmd = args[0]
    if args[1:]:
        params = args[1]
    else:
        params = ''

    # unfold aliases
    if alot.settings.config.has_option('command-aliases', cmd):
        cmd = alot.settings.config.get('command-aliases', cmd)

    # allow to shellescape without a space after '!'
    if cmd.startswith('!'):
        params = cmd[1:] + ' ' + params
        cmd = 'shellescape'

    # check if this command makes sense in current mode
    if cmd not in COMMANDS[mode] and cmd not in COMMANDS['global']:
        logging.debug('unknown command: %s' % (cmd))
        return None

    if cmd == 'search':
        return commandfactory(cmd, mode=mode, query=params)
    if cmd in ['move', 'sendkey']:
        return commandfactory(cmd, mode=mode, key=params)
    elif cmd == 'compose':
        h = {}
        if params:
            h = {'To': params}
        return commandfactory(cmd, mode=mode, headers=h)
    elif cmd == 'attach':
        return commandfactory(cmd, mode=mode, path=params)
    elif cmd == 'help':
        return commandfactory(cmd, mode=mode, commandline=params)
    elif cmd == 'forward':
        return commandfactory(cmd, mode=mode, inline=(params == '--inline'))
    elif cmd == 'prompt':
        return commandfactory(cmd, mode=mode, startstring=params)
    elif cmd == 'refine':
        if mode == 'search':
            return commandfactory(cmd, mode=mode, query=params)
        elif mode == 'envelope':
            return commandfactory(cmd, mode=mode, key=params)

    elif cmd == 'retag':
        return commandfactory(cmd, mode=mode, tagsstring=params)
    elif cmd == 'shellescape':
        return commandfactory(cmd, mode=mode, commandstring=params)
    elif cmd == 'set':
        key, value = params.split(' ', 1)
        return commandfactory(cmd, mode=mode, key=key, value=value)
    elif cmd == 'toggletag':
        return commandfactory(cmd, mode=mode, tags=params.split())
    elif cmd == 'fold':
        return commandfactory(cmd, mode=mode, all=(params == '--all'))
    elif cmd == 'unfold':
        return commandfactory(cmd, mode=mode, all=(params == '--all'))
    elif cmd == 'save':
        args = params.split(' ')
        allset = False
        pathset = None
        if args:
            if args[0] == '--all':
                allset = True
                pathset = ' '.join(args[1:])
            else:
                pathset = params
        return commandfactory(cmd, mode=mode, all=allset, path=pathset)
    elif cmd == 'edit':
        filepath = os.path.expanduser(params)
        if os.path.isfile(filepath):
            return commandfactory(cmd, mode=mode, path=filepath)
    elif cmd == 'print':
        args = [a.strip() for a in params.split()]
        return commandfactory(cmd, mode=mode,
                              whole_thread=('--thread' in args),
                              separately=('--separately' in args))
    elif cmd == 'pipeto':
        return commandfactory(cmd, mode=mode, command=params)

    elif not params and cmd in ['exit', 'flush', 'pyshell', 'taglist',
                                'bclose', 'compose', 'openfocussed',
                                'closefocussed', 'bnext', 'bprevious', 'retag',
                                'refresh', 'bufferlist', 'refineprompt',
                                'reply', 'open', 'groupreply', 'bounce',
                                'openthread', 'toggleheaders', 'send',
                                'cancel', 'reedit', 'select', 'retagprompt']:
        return commandfactory(cmd, mode=mode)
    else:
        return None


__all__ = list(filename[:-3] for filename in glob.glob1(os.path.dirname(__file__), '*.py'))
