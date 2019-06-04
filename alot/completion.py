# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import abc
import argparse
import email.utils
import glob
import logging
import os
import re

from . import crypto
from . import commands
from .buffers import EnvelopeBuffer
from .settings.const import settings
from .utils import argparse as cargparse
from .db.utils import formataddr
from .helper import split_commandline
from .addressbook import AddressbookError
from .errors import CompletionError
from .utils.cached_property import cached_property


class Completer:
    """base class for completers"""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def complete(self, original, pos):
        """returns a list of completions and cursor positions for the
        string original from position pos on.

        :param original: the string to complete
        :type original: str
        :param pos: starting position to complete from
        :type pos: int
        :returns: pairs of completed string and cursor position in the
                  new string
        :rtype: list of (str, int)
        :raises: :exc:`CompletionError`
        """
        pass

    def relevant_part(self, original, pos, sep=' '):
        """
        calculates the subword in a `sep`-splitted list of substrings of
        `original` that `pos` is ia.n
        """
        start = original.rfind(sep, 0, pos) + 1
        end = original.find(sep, pos - 1)
        if end == -1:
            end = len(original)
        return original[start:end], start, end, pos - start


class StringlistCompleter(Completer):
    """completer for a fixed list of strings"""

    def __init__(self, resultlist, ignorecase=True, match_anywhere=False):
        """
        :param resultlist: strings used for completion
        :type resultlist: list of str
        :param liberal: match case insensitive and not prefix-only
        :type liberal: bool
        """
        self.resultlist = resultlist
        self.flags = re.IGNORECASE if ignorecase else 0
        self.match_anywhere = match_anywhere

    def complete(self, original, pos):
        pref = original[:pos]

        re_prefix = '.*' if self.match_anywhere else ''

        def match(s, m):
            r = '{}{}.*'.format(re_prefix, re.escape(m))
            return re.match(r, s, flags=self.flags) is not None

        return [(a, len(a)) for a in self.resultlist if match(a, pref)]


class MultipleSelectionCompleter(Completer):
    """
    Meta-Completer that turns any Completer into one that deals with a list of
    completion strings using the wrapped Completer.
    This allows for example to easily construct a completer for comma separated
    recipient-lists using a :class:`ContactsCompleter`.
    """

    def __init__(self, completer, separator=', '):
        """
        :param completer: completer to use for individual substrings
        :type completer: Completer
        :param separator: separator used to split the completion string into
                          substrings to be fed to `completer`.
        :type separator: str
        """
        self._completer = completer
        self._separator = separator

    def relevant_part(self, original, pos):
        """
        calculates the subword of `original` that `pos` is in
        """
        start = original.rfind(self._separator, 0, pos)
        if start == -1:
            start = 0
        else:
            start = start + len(self._separator)
        end = original.find(self._separator, pos - 1)
        if end == -1:
            end = len(original)
        return original[start:end], start, end, pos - start

    def complete(self, original, pos):
        mypart, start, end, mypos = self.relevant_part(original, pos)
        res = []
        for c, _ in self._completer.complete(mypart, mypos):
            newprefix = original[:start] + c
            if not original[end:].startswith(self._separator):
                newprefix += self._separator
            res.append((newprefix + original[end:], len(newprefix)))
        return res


class NamedQueryCompleter(StringlistCompleter):
    """complete the name of a named query string"""

    def __init__(self, dbman):
        """
        :param dbman: used to look up named query strings in the DB
        :type dbman: :class:`~alot.db.DBManager`
        """
        # mapping of alias to query string (dict str -> str)
        nqueries = dbman.get_named_queries()
        StringlistCompleter.__init__(self, list(nqueries))


class QueryCompleter(Completer):
    """completion for a notmuch query string"""
    def __init__(self, dbman):
        """
        :param dbman: used to look up available tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        """
        self.dbman = dbman
        abooks = settings.get_addressbooks()
        self._abookscompleter = AbooksCompleter(abooks, addressesonly=True)
        self._tagcompleter = TagCompleter(dbman)
        self._nquerycompleter = NamedQueryCompleter(dbman)
        self.keywords = ['tag', 'from', 'to', 'subject', 'attachment',
                         'is', 'id', 'thread', 'folder', 'query']

    def complete(self, original, pos):
        mypart, start, end, mypos = self.relevant_part(original, pos)
        myprefix = mypart[:mypos]
        m = re.search(r'(tag|is|to|from|query):(\w*)', myprefix)
        if m:
            cmd, _ = m.groups()
            cmdlen = len(cmd) + 1  # length of the keyword part including colon
            if cmd in ['to', 'from']:
                localres = self._abookscompleter.complete(mypart[cmdlen:],
                                                          mypos - cmdlen)
            elif cmd in ['query']:
                localres = self._nquerycompleter.complete(mypart[cmdlen:],
                                                          mypos - cmdlen)
            else:
                localres = self._tagcompleter.complete(mypart[cmdlen:],
                                                       mypos - cmdlen)
            resultlist = []
            for ltxt, lpos in localres:
                newtext = original[:start] + cmd + ':' + ltxt + original[end:]
                newpos = start + len(cmd) + 1 + lpos
                resultlist.append((newtext, newpos))
            return resultlist
        else:
            matched = (t for t in self.keywords if t.startswith(myprefix))
            resultlist = []
            for keyword in matched:
                newprefix = original[:start] + keyword + ':'
                resultlist.append((newprefix + original[end:], len(newprefix)))
            return resultlist


class TagCompleter(StringlistCompleter):
    """complete a tagstring"""

    def __init__(self, dbman):
        """
        :param dbman: used to look up available tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        """
        resultlist = dbman.get_all_tags()
        StringlistCompleter.__init__(self, resultlist)


class TagsCompleter(MultipleSelectionCompleter):
    """completion for a comma separated list of tagstrings"""

    def __init__(self, dbman):
        """
        :param dbman: used to look up available tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        """
        self._completer = TagCompleter(dbman)
        self._separator = ','


class ContactsCompleter(MultipleSelectionCompleter):
    """completes contacts from given address books"""
    def __init__(self, abooks, addressesonly=False):
        """
        :param abooks: used to look up email addresses
        :type abooks: list of :class:`~alot.account.AddresBook`
        :param addressesonly: only insert address, not the realname of the
                              contact
        :type addressesonly: bool
        """
        self._completer = AbooksCompleter(abooks, addressesonly=addressesonly)
        self._separator = ', '


class AbooksCompleter(Completer):
    """completes a contact from given address books"""
    def __init__(self, abooks, addressesonly=False):
        """
        :param abooks: used to look up email addresses
        :type abooks: list of :class:`~alot.account.AddresBook`
        :param addressesonly: only insert address, not the realname of the
                              contact
        :type addressesonly: bool
        """
        self.abooks = abooks
        self.addressesonly = addressesonly

    def complete(self, original, pos):
        if not self.abooks:
            return []
        prefix = original[:pos]
        res = []
        for abook in self.abooks:
            try:
                res = res + abook.lookup(prefix)
            except AddressbookError as e:
                raise CompletionError(e)
        if self.addressesonly:
            returnlist = [(addr, len(addr)) for (name, addr) in res]
        else:
            returnlist = []
            for name, addr in res:
                newtext = formataddr((name, addr))
                returnlist.append((newtext, len(newtext)))
        return returnlist


class ArgparseOptionCompleter(Completer):
    """completes option parameters for a given argparse.Parser"""
    def __init__(self, parser):
        """
        :param parser: the option parser we look up parameter and  choices from
        :type parser: `argparse.ArgumentParser`
        """
        self.parser = parser
        self.actions = parser._optionals._actions

    def complete(self, original, pos):
        pref = original[:pos]

        res = []
        for act in self.actions:
            if '=' in pref:
                optionstring = pref[:pref.rfind('=') + 1]
                # get choices
                if 'choices' in act.__dict__:
                    # TODO: respect prefix
                    choices = act.choices or []
                    res = res + [optionstring + a for a in choices]
            else:
                for optionstring in act.option_strings:
                    if optionstring.startswith(pref):
                        # append '=' for options that await a string value
                        if isinstance(act, (argparse._StoreAction,
                                            cargparse.BooleanAction)):
                            optionstring += '='
                        res.append(optionstring)

        return [(a, len(a)) for a in res]


class AccountCompleter(StringlistCompleter):
    """completes users' own mailaddresses"""

    def __init__(self, **kwargs):
        accounts = settings.get_accounts()
        resultlist = [email.utils.formataddr((a.realname, str(a.address)))
                      for a in accounts]
        StringlistCompleter.__init__(self, resultlist, match_anywhere=True,
                                     **kwargs)


class CommandNameCompleter(Completer):
    """completes command names"""

    def __init__(self, mode):
        """
        :param mode: mode identifier
        :type mode: str
        """
        self.mode = mode

    def complete(self, original, pos):
        # TODO refine <tab> should get current querystring
        commandprefix = original[:pos]
        logging.debug('original="%s" prefix="%s"', original, commandprefix)
        cmdlist = commands.COMMANDS['global'].copy()
        cmdlist.update(commands.COMMANDS[self.mode])
        matching = [t for t in cmdlist if t.startswith(commandprefix)]
        return [(t, len(t)) for t in matching]


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

    def complete(self, line, pos):
        # remember how many preceding space characters we see until the command
        # string starts. We'll continue to complete from there on and will add
        # these whitespaces again at the very end
        whitespaceoffset = len(line) - len(line.lstrip())
        line = line[whitespaceoffset:]
        pos = pos - whitespaceoffset

        words = line.split(' ', 1)

        res = []
        if pos <= len(words[0]):  # we complete commands
            for cmd, cpos in self._commandnamecompleter.complete(line, pos):
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
                res = [('%s %s' % (cmd, t), p + len(cmd) +
                        1) for (t, p) in res]

        # re-insert whitespaces and correct position
        wso = whitespaceoffset
        res = [(' ' * wso + cmdstr, p + wso) for cmdstr, p in res]
        return res


class CommandLineCompleter(Completer):
    """completes command lines: semicolon separated command strings"""

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
        self._commandcompleter = CommandCompleter(dbman, mode, currentbuffer)

    @staticmethod
    def get_context(line, pos):
        """
        computes start and end position of substring of line that is the
        command string under given position
        """
        commands = split_commandline(line) + ['']
        i = 0
        start = 0
        end = len(commands[i])
        while pos > end:
            i += 1
            start = end + 1
            end += 1 + len(commands[i])
        return start, end

    def complete(self, line, pos):
        cstart, cend = self.get_context(line, pos)
        before = line[:cstart]
        after = line[cend:]
        cmdstring = line[cstart:cend]
        cpos = pos - cstart

        res = []
        for ccmd, ccpos in self._commandcompleter.complete(cmdstring, cpos):
            newtext = before + ccmd + after
            newpos = pos + (ccpos - cpos)
            res.append((newtext, newpos))
        return res


class PathCompleter(Completer):

    """completion for paths"""

    def complete(self, original, pos):
        if not original:
            return [('~/', 2)]
        prefix = os.path.expanduser(original[:pos])

        def escape(path):
            """Escape all backslashes and spaces in given path with a
            backslash.

            :param path: the path to escape
            :type path: str
            :returns: the escaped path
            :rtype: str
            """
            return path.replace('\\', '\\\\').replace(' ', r'\ ')

        def deescape(escaped_path):
            """Remove escaping backslashes in front of spaces and backslashes.

            :param escaped_path: a path potentially with escaped spaces and
                backslashs
            :type escaped_path: str
            :returns: the actual path
            :rtype: str
            """
            return escaped_path.replace('\\ ', ' ').replace('\\\\', '\\')

        def prep(path):
            escaped_path = escape(path)
            return escaped_path, len(escaped_path)

        return [prep(g) for g in glob.glob(deescape(prefix) + '*')]


class CryptoKeyCompleter(StringlistCompleter):
    """completion for gpg keys"""

    def __init__(self, private=False):
        """
        :param private: return private keys
        :type private: bool
        """
        keys = crypto.list_keys(private=private)
        resultlist = []
        for k in keys:
            for s in k.subkeys:
                resultlist.append(s.keyid)
            for u in k.uids:
                resultlist.append(u.email)
        StringlistCompleter.__init__(self, resultlist, match_anywhere=True)
