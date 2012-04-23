import re
import os
import glob
import logging
import argparse

import alot.commands as commands
from alot.buffers import EnvelopeBuffer
from alot.settings import settings


class Completer(object):
    """base class for completers"""
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
        """
        return list()

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

    def __init__(self, resultlist):
        """
        :param resultlist: strings used for completion
        :type resultlist: list of str
        """
        self.resultlist = resultlist

    def complete(self, original, pos):
        pref = original[:pos]
        return [(a, len(a)) for a in self.resultlist if a.startswith(pref)]


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
        for c, p in self._completer.complete(mypart, mypos):
            newprefix = original[:start] + c
            if not original[end:].startswith(self._separator):
                newprefix += self._separator
            res.append((newprefix + original[end:], len(newprefix)))
        return res


class QueryCompleter(Completer):
    """completion for a notmuch query string"""
    def __init__(self, dbman):
        """
        :param dbman: used to look up avaliable tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        """
        self.dbman = dbman
        abooks = settings.get_addressbooks()
        self._abookscompleter = AbooksCompleter(abooks, addressesonly=True)
        self._tagcompleter = TagCompleter(dbman)
        self.keywords = ['tag', 'from', 'to', 'subject', 'attachment',
                         'is', 'id', 'thread', 'folder']

    def complete(self, original, pos):
        mypart, start, end, mypos = self.relevant_part(original, pos)
        myprefix = mypart[:mypos]
        m = re.search('(tag|is|to|from):(\w*)', myprefix)
        if m:
            cmd, params = m.groups()
            cmdlen = len(cmd) + 1  # length of the keyword part incld colon
            if cmd in ['to', 'from']:
                localres = self._abookscompleter.complete(mypart[cmdlen:],
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
            matched = filter(lambda t: t.startswith(myprefix), self.keywords)
            resultlist = []
            for keyword in matched:
                newprefix = original[:start] + keyword + ':'
                resultlist.append((newprefix + original[end:], len(newprefix)))
            return resultlist


class TagCompleter(StringlistCompleter):
    """complete a tagstring"""

    def __init__(self, dbman):
        """
        :param dbman: used to look up avaliable tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        """
        resultlist = dbman.get_all_tags()
        StringlistCompleter.__init__(self, resultlist)


class TagsCompleter(MultipleSelectionCompleter):
    """completion for a comma separated list of tagstrings"""

    def __init__(self, dbman):
        """
        :param dbman: used to look up avaliable tagstrings
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
            res = res + abook.lookup(prefix)
        if self.addressesonly:
            returnlist = [(email, len(email)) for (name, email) in res]
        else:
            returnlist = []
            for name, email in res:
                if name:
                    newtext = "%s <%s>" % (name, email)
                else:
                    newtext = email
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
                    choices = act.choices or []
                    res = res + [optionstring + a for a in choices]
            else:
                for optionstring in act.option_strings:
                    if optionstring.startswith(pref):
                        # append '=' for options that await a string value
                        if isinstance(act, argparse._StoreAction):
                            optionstring += '='
                        res.append(optionstring)

        return [(a, len(a)) for a in res]


class AccountCompleter(StringlistCompleter):
    """completes users' own mailaddresses"""

    def __init__(self):
        resultlist = settings.get_main_addresses()
        StringlistCompleter.__init__(self, resultlist)


class CommandCompleter(Completer):
    """completes commands"""

    def __init__(self, mode):
        """
        :param mode: mode identifier
        :type mode: str
        """
        self.mode = mode

    def complete(self, original, pos):
        #TODO refine <tab> should get current querystring
        commandprefix = original[:pos]
        logging.debug('original="%s" prefix="%s"' % (original, commandprefix))
        cmdlist = commands.COMMANDS['global'].copy()
        cmdlist.update(commands.COMMANDS[self.mode])
        matching = [t for t in cmdlist if t.startswith(commandprefix)]
        return [(t, len(t)) for t in matching]


class CommandLineCompleter(Completer):
    """completion for commandline"""

    def __init__(self, dbman, mode, currentbuffer=None):
        """
        :param dbman: used to look up avaliable tagstrings
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
        self._commandcompleter = CommandCompleter(mode)
        self._querycompleter = QueryCompleter(dbman)
        self._tagcompleter = TagCompleter(dbman)
        abooks = settings.get_addressbooks()
        self._contactscompleter = ContactsCompleter(abooks)
        self._pathcompleter = PathCompleter()

    def complete(self, line, pos):
        words = line.split(' ', 1)

        res = []
        if pos <= len(words[0]):  # we complete commands
            for cmd, cpos in self._commandcompleter.complete(line, pos):
                newtext = ('%s %s' % (cmd, ' '.join(words[1:])))
                res.append((newtext, cpos + 1))
        else:
            cmd, params = words
            localpos = pos - (len(cmd) + 1)
            parser = commands.lookup_parser(cmd, self.mode)
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
            # 1. all arguments prior to current position are optional parameter
            # 2. the parameter starts with '-' or we are at its beginning
            if all_optionals:
                myarg = arguments_until_now[-1]
                start_myarg = params.rindex(myarg)
                beforeme = params[:start_myarg]
                # set up local stringlist completer
                # and let it complete for given list of options
                localcompleter = ArgparseOptionCompleter(parser)
                localres = localcompleter.complete(myarg, len(myarg))
                res = [(beforeme + c, p + start_myarg) for (c, p) in localres]

            # global
            elif cmd == 'search':
                res = self._querycompleter.complete(params, localpos)
            elif cmd == 'help':
                res = self._commandcompleter.complete(params, localpos)
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
                    headers = ['Subject', 'To', 'Cc', 'Bcc', 'In-Reply-To']
                    localcompleter = StringlistCompleter(headers)
                    localres = localcompleter.complete(localprefix, localpos)
                    res = [(c, p + 6) for (c, p) in localres]
                else:  # must have 2 elements
                    header, params = plist
                    localpos = localpos - (len(header) + 1)
                    if header.lower() in ['to', 'cc', 'bcc']:

                        # prepend 'set ' + header and correct position
                        def f((completed, pos)):
                            return ('%s %s' % (header, completed),
                                    pos + len(header) + 1)
                        res = map(f, self._contactscompleter.complete(params,
                                                                  localpos))
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
            # thread
            elif self.mode == 'thread' and cmd == 'save':
                res = self._pathcompleter.complete(params, localpos)
            elif self.mode == 'thread' and cmd in ['tag', 'retag', 'untag',
                                                   'toggletags']:
                localcomp = MultipleSelectionCompleter(self._tagcompleter,
                                                       separator=',')
                res = localcomp.complete(params, localpos)

            # prepend cmd and correct position
            res = [('%s %s' % (cmd, t), p + len(cmd) + 1) for (t, p) in res]
        return res


class PathCompleter(Completer):
    """completion for paths"""
    def complete(self, original, pos):
        if not original:
            return [('~/', 2)]
        prefix = os.path.expanduser(original[:pos])

        def escape(path):
            return path.replace('\\', '\\\\').replace(' ', '\ ')

        def deescape(escaped_path):
            return escaped_path.replace('\\ ', ' ').replace('\\\\', '\\')

        def prep(path):
            escaped_path = escape(path)
            return escaped_path, len(escaped_path)

        return map(prep, glob.glob(deescape(prefix) + '*'))
