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


from settings import hooks
import command
import envelope

COMMANDS = {
        'bnext': (command.BufferFocusCommand, {'offset': 1}),
        'bprevious': (command.BufferFocusCommand, {'offset': -1}),
        'bufferlist': (command.OpenBufferListCommand, {}),
        'close': (command.BufferCloseCommand, {}),
        'closefocussed': (command.BufferCloseCommand, {'focussed': True}),
        'openfocussed': (command.BufferFocusCommand, {}),
        'commandprompt': (command.CommandPromptCommand, {}),
        'compose': (command.ComposeCommand, {}),
        'edit': (command.EditCommand, {}),
        'exit': (command.ExitCommand, {}),
        'flush': (command.FlushCommand, {}),
        'openthread': (command.OpenThreadCommand, {}),
        'prompt': (command.PromptCommand, {}),
        'pyshell': (command.PythonShellCommand, {}),
        'refine': (command.RefineCommand, {}),
        'refineprompt': (command.RefinePromptCommand, {}),
        'refresh': (command.RefreshCommand, {}),
        'search': (command.SearchCommand, {}),
        'shellescape': (command.ExternalCommand, {}),
        'taglist': (command.TagListCommand, {}),
        'toggletag': (command.ToggleThreadTagCommand, {'tag': 'inbox'}),
        # envelope
        'send': (envelope.SendMailCommand, {}),
        'reedit': (envelope.EnvelopeEditCommand, {}),
        'subject': (envelope.EnvelopeSetCommand, {'key': 'Subject'}),
        'to': (envelope.EnvelopeSetCommand, {'key': 'To'}),

        'open_envelope': (command.OpenEnvelopeCommand, {}),
        'retag': (command.RetagCommand, {}),
        'retagprompt': (command.RetagPromptCommand, {}),
        # thread
        'reply': (command.ReplyCommand, {}),
        'groupreply': (command.ReplyCommand, {'groupreply': True}),
        'bounce': (command.BounceMailCommand, {}),

        # taglist
        'select': (command.TaglistSelectCommand, {}),
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

        parms['prehook'] = hooks.get('pre_' + cmdname)
        parms['posthook'] = hooks.get('post_' + cmdname)

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
    'search': ['refine', 'refineprompt', 'toggletag', 'openthread', 'retag',
               'retagprompt'] + globalcomands,
    'envelope': ['send', 'reedit', 'to', 'subject'] + globalcomands,
    'bufferlist': ['openfocussed', 'closefocussed'] + globalcomands,
    'taglist': ['select'] + globalcomands,
    'thread': ['toggletag', 'reply', 'groupreply', 'bounce'] + globalcomands,
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
        if cmd in ['exit', 'flush', 'pyshell', 'taglist', 'close', 'compose',
                   'openfocussed', 'closefocussed', 'bnext', 'bprevious',
                   'retag', 'refresh', 'bufferlist', 'refineprompt', 'reply',
                   'groupreply', 'bounce', 'openthread', 'send', 'reedit',
                   'select', 'retagprompt']:
            return commandfactory(cmd)
        else:
            return None
    else:
        if cmd == 'search':
            return commandfactory(cmd, query=params)
        elif cmd == 'compose':
            return commandfactory(cmd, headers={'To': params})
        elif cmd == 'prompt':
            return commandfactory(cmd, startstring=params)
        elif cmd == 'refine':
            return commandfactory(cmd, query=params)
        elif cmd == 'retag':
            return commandfactory(cmd, tagsstring=params)
        elif cmd == 'subject':
            return commandfactory(cmd, key='Subject', value=params)
        elif cmd == 'shellescape':
            return commandfactory(cmd, commandstring=params)
        elif cmd == 'to':
            return commandfactory(cmd, key='To', value=params)
        elif cmd == 'toggletag':
            return commandfactory(cmd, tag=params)
        elif cmd == 'edit':
            filepath = params[0]
            if os.path.isfile(filepath):
                return commandfactory(cmd, path=filepath)
        else:
            return None
