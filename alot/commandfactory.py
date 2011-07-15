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


from settings import get_hook
import commands

commands = {
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

        'buffer_focus': (commands.BufferFocusCommand, {}),
        'compose': (commands.ComposeCommand, {}),
        'open_thread': (commands.OpenThreadCommand, {}),
        'open_envelope': (commands.OpenEnvelopeCommand, {}),
        'search prompt': (commands.SearchPromptCommand, {}),
        'refine_search_prompt': (commands.RefineSearchPromptCommand, {}),
        'send': (commands.SendMailCommand, {}),
        'thread_tag_prompt': (commands.ThreadTagPromptCommand, {}),
        'toggle_thread_tag': (commands.ToggleThreadTagCommand, {'tag': 'inbox'}),
        }


def commandfactory(cmdname, **kwargs):
    if cmdname in commands:
        (cmdclass, parms) = commands[cmdname]
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


def interpret_commandline(cmdline):
    if not cmdline:
        return None
    logging.debug(cmdline + '"')
    args = cmdline.strip().split(' ', 1)
    cmd = args[0]
    params = args[1:]

    # unfold aliases
    if cmd in aliases:
        cmd = aliases[cmd]

    # buffer commands depend on first parameter only
    if cmd == 'buffer' and (params) == 1:
        cmd = cmd + params[0]
    # allow to shellescape without a space after '!'
    if cmd.startswith('!'):
        params = cmd[1:] + ''.join(params)
        cmd = 'shellescape'

    if not params:
        if cmd in ['exit', 'flush', 'pyshell', 'taglist', 'buffer close',
                  'buffer next', 'buffer previous', 'buffer refresh',
                   'bufferlist']:
            return commandfactory(cmd)
        else:
            return None
    else:
        if cmd == 'search':
            return commandfactory(cmd, query=params[0])
        elif cmd == 'shellescape':
            return commandfactory(cmd, commandstring=params)
        elif cmd == 'edit':
            filepath = params[0]
            if os.path.isfile(filepath):
                return commandfactory(cmd, path=filepath)

        else:
            return None
