# Copyright (C) 2011-2019  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import logging

from alot import commands
from alot.buffers import EnvelopeBuffer
from alot.settings.const import settings
from alot.utils.cached_property import cached_property
from .completer import Completer
from .commandname import CommandNameCompleter
from .tag import TagCompleter
from .query import QueryCompleter
from .contacts import ContactsCompleter
from .accounts import AccountCompleter
from .path import PathCompleter
from .stringlist import StringlistCompleter
from .multipleselection import MultipleSelectionCompleter
from .cryptokey import CryptoKeyCompleter
from .argparse import ArgparseOptionCompleter


class CommandCompleter(Completer):
    """completes one command consisting of command name and parameters"""

    def __init__(self, dbman, mode, currentbuffer=None):
        """
        :param dbman: used to look up available tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        :param mode: mode identifier
        :type mode: str
        :param currentbuffer: currently active buffer. If defined, this will be
                              used to dynamically extract possible completion
                              strings
        :type currentbuffer: :class:`~alot.buffers.Buffer`
        """
        self.dbman = dbman
        self.mode = mode
        self.currentbuffer = currentbuffer
        self._commandnamecompleter = CommandNameCompleter(mode)

    @cached_property
    def _querycompleter(self):
        return QueryCompleter(self.dbman)

    @cached_property
    def _tagcompleter(self):
        return TagCompleter(self.dbman)

    @cached_property
    def _contactscompleter(self):
        abooks = settings.get_addressbooks()
        return ContactsCompleter(abooks)

    @cached_property
    def _pathcompleter(self):
        return PathCompleter()

    @cached_property
    def _accountscompleter(self):
        return AccountCompleter()

    @cached_property
    def _secretkeyscompleter(self):
        return CryptoKeyCompleter(private=True)

    @cached_property
    def _publickeyscompleter(self):
        return CryptoKeyCompleter(private=False)

    def complete(self, original, pos):
        # remember how many preceding space characters we see until the command
        # string starts. We'll continue to complete from there on and will add
        # these whitespaces again at the very end
        whitespaceoffset = len(original) - len(original.lstrip())
        original = original[whitespaceoffset:]
        pos = pos - whitespaceoffset

        words = original.split(' ', 1)

        res = []
        if pos <= len(words[0]):  # we complete commands
            for cmd, cpos in self._commandnamecompleter.complete(original,
                                                                 pos):
                newtext = ('%s %s' % (cmd, ' '.join(words[1:])))
                res.append((newtext, cpos + 1))
        else:
            cmd, params = words
            localpos = pos - (len(cmd) + 1)
            parser = commands.lookup_parser(cmd, self.mode)
            if parser is not None:
                # set 'res' - the result set of matching completionstrings
                # depending on the current mode and command

                # detect if we are completing optional parameter
                arguments_until_now = params[:localpos].split(' ')
                all_optionals = True
                logging.debug(str(arguments_until_now))
                for a in arguments_until_now:
                    logging.debug(a)
                    if a and not a.startswith('-'):
                        all_optionals = False
                # complete optional parameter if
                # 1. all arguments prior to current position are optional
                # 2. the parameter starts with '-' or we are at its beginning
                if all_optionals:
                    myarg = arguments_until_now[-1]
                    start_myarg = params.rindex(myarg)
                    beforeme = params[:start_myarg]
                    # set up local stringlist completer
                    # and let it complete for given list of options
                    localcompleter = ArgparseOptionCompleter(parser)
                    localres = localcompleter.complete(myarg, len(myarg))
                    res = [(
                        beforeme + c, p + start_myarg) for (c, p) in localres]

                # global
                elif cmd == 'search':
                    res = self._querycompleter.complete(params, localpos)
                elif cmd == 'help':
                    res = self._commandnamecompleter.complete(params, localpos)
                elif cmd in ['compose']:
                    res = self._contactscompleter.complete(params, localpos)
                # search
                elif self.mode == 'search' and cmd == 'refine':
                    res = self._querycompleter.complete(params, localpos)
                elif self.mode == 'search' and cmd in ['tag', 'retag', 'untag',
                                                       'toggletags']:
                    localcomp = MultipleSelectionCompleter(self._tagcompleter,
                                                           separator=',')
                    res = localcomp.complete(params, localpos)
                elif self.mode == 'search' and cmd == 'toggletag':
                    localcomp = MultipleSelectionCompleter(self._tagcompleter,
                                                           separator=' ')
                    res = localcomp.complete(params, localpos)
                # envelope
                elif self.mode == 'envelope' and cmd == 'set':
                    plist = params.split(' ', 1)
                    if len(plist) == 1:  # complete from header keys
                        localprefix = params
                        headers = ['Subject', 'To', 'Cc', 'Bcc', 'In-Reply-To',
                                   'From']
                        localcompleter = StringlistCompleter(headers)
                        localres = localcompleter.complete(
                            localprefix, localpos)
                        res = [(c, p + 6) for (c, p) in localres]
                    else:  # must have 2 elements
                        header, params = plist
                        localpos = localpos - (len(header) + 1)
                        if header.lower() in ['to', 'cc', 'bcc']:
                            res = self._contactscompleter.complete(params,
                                                                   localpos)
                        elif header.lower() == 'from':
                            res = self._accountscompleter.complete(params,
                                                                   localpos)

                        # prepend 'set ' + header and correct position
                        def f(completed, pos):
                            return ('%s %s' % (header, completed),
                                    pos + len(header) + 1)
                        res = [f(c, p) for c, p in res]
                        logging.debug(res)

                elif self.mode == 'envelope' and cmd == 'unset':
                    plist = params.split(' ', 1)
                    if len(plist) == 1:  # complete from header keys
                        localprefix = params
                        buf = self.currentbuffer
                        if buf:
                            if isinstance(buf, EnvelopeBuffer):
                                available = buf.envelope.headers.keys()
                                localcompleter = StringlistCompleter(available)
                                localres = localcompleter.complete(localprefix,
                                                                   localpos)
                                res = [(c, p + 6) for (c, p) in localres]

                elif self.mode == 'envelope' and cmd == 'attach':
                    res = self._pathcompleter.complete(params, localpos)
                elif self.mode == 'envelope' and cmd in ['sign', 'togglesign']:
                    res = self._secretkeyscompleter.complete(params, localpos)
                elif self.mode == 'envelope' and cmd in ['encrypt',
                                                         'rmencrypt',
                                                         'toggleencrypt']:
                    res = self._publickeyscompleter.complete(params, localpos)
                elif self.mode == 'envelope' and cmd in ['tag', 'toggletags',
                                                         'untag', 'retag']:
                    localcomp = MultipleSelectionCompleter(self._tagcompleter,
                                                           separator=',')
                    res = localcomp.complete(params, localpos)
                # thread
                elif self.mode == 'thread' and cmd == 'save':
                    res = self._pathcompleter.complete(params, localpos)
                elif self.mode == 'thread' and cmd in ['fold', 'unfold',
                                                       'togglesource',
                                                       'toggleheaders']:
                    res = self._querycompleter.complete(params, localpos)
                elif self.mode == 'thread' and cmd in ['tag', 'retag', 'untag',
                                                       'toggletags']:
                    localcomp = MultipleSelectionCompleter(self._tagcompleter,
                                                           separator=',')
                    res = localcomp.complete(params, localpos)
                elif cmd == 'move':
                    directions = ['up', 'down', 'page up', 'page down',
                                  'halfpage up', 'halfpage down', 'first',
                                  'last']
                    if self.mode == 'thread':
                        directions += ['parent', 'first reply', 'last reply',
                                       'next sibling', 'previous sibling',
                                       'next', 'previous', 'next unfolded',
                                       'previous unfolded']
                    localcompleter = StringlistCompleter(directions)
                    res = localcompleter.complete(params, localpos)

                # prepend cmd and correct position
                res = [('%s %s' % (cmd, t), p + len(cmd) + 1)
                       for (t, p) in res]

        # re-insert whitespaces and correct position
        wso = whitespaceoffset
        res = [(' ' * wso + cmdstr, p + wso) for cmdstr, p in res]
        return res
