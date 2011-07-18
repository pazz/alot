"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Alot is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
import logging
import os


from settings import get_hook
import commands

COMMANDS = {
        'bnext': (commands.BufferFocusCommand, {'offset': 1}),
        'bprevious': (commands.BufferFocusCommand, {'offset': -1}),
        'bufferfocus': (commands.BufferFocusCommand, {}),
        'bufferlist': (commands.OpenBufferListCommand, {}),
        'close': (commands.BufferCloseCommand, {}),
        'closefocussed': (commands.BufferCloseCommand, {'focussed': True}),
        'commandprompt': (commands.CommandPromptCommand, {}),
        'edit': (commands.EditCommand, {}),
        'exit': (commands.ExitCommand, {}),
        'flush': (commands.FlushCommand, {}),
        'openthread': (commands.OpenThreadCommand, {}),
        'prompt': (commands.PromptCommand, {}),
        'pyshell': (commands.PythonShellCommand, {}),
        'refine': (commands.RefineCommand, {}),
        'refineprompt': (commands.RefinePromptCommand, {}),
        'refresh': (commands.RefreshCommand, {}),
        'search': (commands.SearchCommand, {}),
        'shellescape': (commands.ExternalCommand, {}),
        'taglist': (commands.TagListCommand, {}),
        'toggletag': (commands.ToggleThreadTagCommand, {'tag': 'inbox'}),

        'compose': (commands.ComposeCommand, {}),
        'open_envelope': (commands.OpenEnvelopeCommand, {}),
        'send': (commands.SendMailCommand, {}),
        'retag': (commands.RetagCommand, {}),
        'retagprompt': (commands.RetagPromptCommand, {}),
        }


def commandfactory(cmdname, **kwargs):
    if cmdname in COMMANDS:
        (cmdclass, parms) = COMMANDS[cmdname]
        parms = parms.copy()
        parms.update(kwargs)
        for (key, value) in kwargs.items():
            if callable(value):
                parms[key] = value()
            else:
                parms[key] = value

        parms['prehook'] = get_hook('pre_' + cmdname)
        parms['posthook'] = get_hook('post_' + cmdname)

        logging.debug('cmd parms %s' % parms)
        return cmdclass(**parms)
    else:
        logging.error('there is no command %s' % cmdname)


aliases = {'clo': 'close',
           'bn': 'bnext',
           'bp': 'bprevious',
           'bcf': 'buffer close focussed',
           'ls': 'bufferlist',
           'quit': 'exit',
}

globalcomands = [
    'bnext',
    'bprevious',
    'bufferlist',
    'close',
    'compose',
    'prompt',
    'edit',
    'exit',
    'flush',
    'pyshell',
    'refresh',
    'search',
    'shellescape',
    'taglist',
]

ALLOWED_COMMANDS = {
    'search': ['refine', 'refineprompt', 'toggletag', 'openthread', 'retag', 'retagprompt'] + globalcomands,
    'envelope': ['send'] + globalcomands,
    'bufferlist': ['bufferfocussed', 'closefocussed'] + globalcomands,
    'taglist': globalcomands,
    'thread': ['toggletag'] + globalcomands,
}


def interpret_commandline(cmdline, mode):
    if not cmdline:
        return None
    logging.debug('mode:%s got commandline "%s"' % (mode, cmdline))
    args = cmdline.strip().split(' ', 1)
    cmd = args[0]
    if args[1:]:
        params = args[1]
    else:
        params = ''

    # unfold aliases
    if cmd in aliases:
        cmd = aliases[cmd]

    # allow to shellescape without a space after '!'
    if cmd.startswith('!'):
        params = cmd[1:] + params
        cmd = 'shellescape'

    # check if this command makes sense in current mode
    if cmd not in ALLOWED_COMMANDS[mode]:
        logging.debug('not allowed in mode %s: %s' % (mode, cmd))
        return None

    if not params:  # commands that work without parameter
        if cmd in ['exit', 'flush', 'pyshell', 'taglist', 'close',
                   'closefocussed', 'bnext', 'bprevious', 'retag',
                   'refresh', 'bufferlist', 'refineprompt', 'openthread',
                   'bufferfocus', 'retagprompt']:
            return commandfactory(cmd)
        else:
            return None
    else:
        if cmd == 'search':
            return commandfactory(cmd, query=params)
        elif cmd == 'prompt':
            return commandfactory(cmd, startstring=params)
        elif cmd == 'refine':
            return commandfactory(cmd, query=params)
        elif cmd == 'retag':
            return commandfactory(cmd, tagsstring=params)
        elif cmd == 'shellescape':
            return commandfactory(cmd, commandstring=params)
        elif cmd == 'toggletag':
            return commandfactory(cmd, tag=params)
        elif cmd == 'edit':
            filepath = params[0]
            if os.path.isfile(filepath):
                return commandfactory(cmd, path=filepath)
        else:
            return None
