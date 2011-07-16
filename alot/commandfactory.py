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
        'bufferlist': (commands.OpenBufferListCommand, {}),
        'buffer close': (commands.BufferCloseCommand, {}),
        'buffer next': (commands.BufferFocusCommand, {'offset': 1}),
        'buffer refresh': (commands.RefreshCommand, {}),
        'buffer previous': (commands.BufferFocusCommand, {'offset': -1}),
        'exit': (commands.ExitCommand, {}),
        'flush': (commands.FlushCommand, {}),
        'pyshell': (commands.PythonShellCommand, {}),
        'search': (commands.SearchCommand, {}),
        'shellescape': (commands.ExternalCommand, {}),
        'taglist': (commands.TagListCommand, {}),
        'edit': (commands.EditCommand, {}),
        'commandprompt': (commands.CommandPromptCommand, {}),
        'openthread': (commands.OpenThreadCommand, {}),
        'refine': (commands.RefineSearchPromptCommand, {}),
        'toggletag': (commands.ToggleThreadTagCommand, {'tag': 'inbox'}),

        'buffer focus': (commands.BufferFocusCommand, {}),
        'compose': (commands.ComposeCommand, {}),
        'open_envelope': (commands.OpenEnvelopeCommand, {}),
        'searchprompt': (commands.SearchPromptCommand, {}),
        'send': (commands.SendMailCommand, {}),
        'thread_tag_prompt': (commands.ThreadTagPromptCommand, {}),
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


aliases = {'bc': 'buffer close',
           'bn': 'buffer next',
           'bp': 'buffer previous',
           'br': 'buffer refresh',
           'refresh': 'buffer refresh',
           'ls': 'bufferlist',
           'quit': 'exit',
}

globalcomands = [
    'buffer close',
    'buffer next',
    'buffer previous',
    'buffer refresh',
    'bufferlist',
    'edit',
    'exit',
    'flush',
    'pyshell',
    'search',
    'shellescape',
    'taglist',
]

ALLOWED_COMMANDS = {
    'search': ['refine', 'toggletag', 'openthread'] + globalcomands,
    'envelope': ['send'] + globalcomands,
    'bufferlist': ['buffer focus'] + globalcomands,
    'taglist': globalcomands,
    'thread': ['toggletag'] + globalcomands,
}

def interpret_commandline(cmdline, mode):
    if not cmdline:
        return None
    logging.debug('mode:%s got commandline "%s"' % (mode, cmdline))
    args = cmdline.strip().split(' ', 1)
    cmd = args[0]
    params = args[1:]

    # unfold aliases
    if cmd in aliases:
        cmd = aliases[cmd]

    # buffer commands depend on first parameter only
    if cmd == 'buffer' and len(params) == 1:
        cmd = cmd + ' ' +params[0]
        params = []
    # allow to shellescape without a space after '!'
    if cmd.startswith('!'):
        params = cmd[1:] + ''.join(params)
        cmd = 'shellescape'

    # check if this command makes sense in current mode
    if cmd not in ALLOWED_COMMANDS[mode]:
        logging.debug('not allowed in mode %s: %s' % (mode,cmd))
        return None

    if not params:
        if cmd in ['exit', 'flush', 'pyshell', 'taglist', 'buffer close',
                   'buffer next', 'buffer previous', 'buffer refresh',
                   'bufferlist', 'refine', 'openthread', 'buffer focus']:
            return commandfactory(cmd)
        else:
            return None
    else:
        if cmd == 'search':
            return commandfactory(cmd, query=params[0])
        elif cmd == 'refine':
            return commandfactory(cmd, query=params[0])
        elif cmd == 'shellescape':
            return commandfactory(cmd, commandstring=params)
        elif cmd == 'toggletag':
            return commandfactory(cmd, tag=params[0])
        elif cmd == 'edit':
            filepath = params[0]
            if os.path.isfile(filepath):
                return commandfactory(cmd, path=filepath)
        else:
            return None
