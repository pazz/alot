import re
import os
import glob
import logging

import alot.commands as commands


class Completer(object):
    """base class for completers"""
    def complete(self, original, pos):
        """returns a list of completions and cursor positions for the
        string original from position pos on.

        :param original: the string to complete
        :type original: str
        :param pos: starting position to complete from
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


class QueryCompleter(Completer):
    """completion for a notmuch query string"""
    def __init__(self, dbman, accountman):
        """
        :param dbman: used to look up avaliable tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        :param accountman: used to look up known addresses to complete 'from'
                           and 'to' queries
        :type accountman: :class:`~alot.account.AccountManager`
        """
        self.dbman = dbman
        abooks = accountman.get_addressbooks()
        self._contactscompleter = ContactsCompleter(abooks, addressesonly=True)
        self._tagscompleter = TagsCompleter(dbman)
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
                localres = self._contactscompleter.complete(mypart[cmdlen:],
                                                            mypos - cmdlen)
            else:
                localres = self._tagscompleter.complete(mypart[cmdlen:],
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


class TagsCompleter(Completer):
    """completion for a comma separated list of tagstrings"""

    def __init__(self, dbman):
        """
        :param dbman: used to look up avaliable tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        """
        self.dbman = dbman

    def complete(self, original, pos, single_tag=True):
        tags = self.dbman.get_all_tags()
        if single_tag:
            prefix = original[:pos]
            matching = [t for t in tags if t.startswith(prefix)]
            return [(t, len(t)) for t in matching]
        else:
            mypart, start, end, mypos = self.relevant_part(original, pos,
                                                           sep=',')
            prefix = mypart[:mypos]
            res = []
            for tag in tags:
                if tag.startswith(prefix):
                    newprefix = original[:start] + tag
                    if not original[end:].startswith(','):
                        newprefix += ','
                    res.append((newprefix + original[end:], len(newprefix)))
            return res


class ContactsCompleter(Completer):
    """completes contacts"""
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
                newtext = "%s <%s>" % (name, email)
                returnlist.append((newtext, len(newtext)))
        return returnlist


class AccountCompleter(Completer):
    """completes users' own mailaddresses"""

    def __init__(self, accountman):
        """
        :param accountman: used to look up the list of addresses
        :type accountman: :class:`~alot.account.AccountManager`
        """
        self.accountman = accountman

    def complete(self, original, pos):
        valids = self.accountman.get_main_addresses()
        prefix = original[:pos]
        return [(a, len(a)) for a in valids if a.startswith(prefix)]


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

    def __init__(self, dbman, accountman, mode):
        """
        :param dbman: used to look up avaliable tagstrings
        :type dbman: :class:`~alot.db.DBManager`
        :param accountman: used to look up known addresses to complete 'from'
                           and 'to' queries
        :type accountman: :class:`~alot.account.AccountManager`
        :param mode: mode identifier
        :type mode: str
        """
        self.dbman = dbman
        self.accountman = accountman
        self.mode = mode
        self._commandcompleter = CommandCompleter(mode)
        self._querycompleter = QueryCompleter(dbman, accountman)
        self._tagscompleter = TagsCompleter(dbman)
        abooks = accountman.get_addressbooks()
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
            if cmd == 'search':
                res = self._querycompleter.complete(params, localpos)
            elif cmd == 'refine':
                if self.mode == 'search':
                    res = self._querycompleter.complete(params, localpos)
            elif cmd == 'set' and self.mode == 'envelope':
                plist = params.split(' ', 1)
                if len(plist) == 1:  # complete from header keys
                    pass
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

                logging.debug(res)
            elif cmd == 'retag':
                res = self._tagscompleter.complete(params, localpos,
                                                   single_tag=False)
            elif cmd == 'toggletag':
                res = self._tagscompleter.complete(params, localpos)
            elif cmd == 'help':
                res = self._commandcompleter.complete(params, localpos)
            elif cmd in ['compose']:
                res = self._contactscompleter.complete(params, localpos)
            elif cmd in ['attach', 'edit', 'save']:
                res = self._pathcompleter.complete(params, localpos)
            # prepend cmd and correct position
            res = [('%s %s' % (cmd, t), p + len(cmd) + 1) for (t, p) in res]
        return res


class PathCompleter(Completer):
    """completion for paths"""
    def complete(self, original, pos):
        if not original:
            return [('~/', 2)]
        prefix = os.path.expanduser(original[:pos])
        return [(f, len(f)) for f in glob.glob(prefix + '*')]
