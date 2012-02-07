import sys
import os
HERE = os.path.dirname(__file__)
sys.path.append(os.path.join(HERE, '..', '..', '..'))
from alot.commands import *
from alot.commands import COMMANDS
import alot.buffers
from argparse import HelpFormatter, SUPPRESS, OPTIONAL, ZERO_OR_MORE, ONE_OR_MORE, PARSER, REMAINDER
from gettext import gettext as _
import collections as _collections
import copy as _copy
import os as _os
import re as _re
import sys as _sys
import textwrap as _textwrap

#print """
#********
#Commands
#********
#"""

class HF(HelpFormatter):
    def _metavar_formatter(self, action, default_metavar):
        if action.metavar is not None:
            result = action.metavar
        else:
            result = default_metavar

        def format(tuple_size):
            if isinstance(result, tuple):
                return result
            else:
                return (result, ) * tuple_size
        return format


def rstify_parser(parser):
        #header = parser.format_usage().strip()
        #print '\n\n%s\n' % header + '_' * len(header)
        parser.formatter_class = HF
        #parser.print_help()
        #continue

        formatter = parser._get_formatter()
        out = ""

        # usage
        usage = formatter._format_usage(None, parser._actions,
                                         parser._mutually_exclusive_groups,
                                        '').strip()
        usage = usage.replace('--','---')

        # section header
        out += '.. index:: %s\n' % parser.prog
        out +='\n%s\n' % parser.prog
        out += '_'*len(parser.prog)
        out += '\n\n'

        # description
        out += parser.description
        out += '\n\n'

        if len(parser._positionals._group_actions) == 1:
            out += "argument\n"
            a = parser._positionals._group_actions[0]
            out += "\t%s" % parser._positionals._group_actions[0].help
            if a.choices:
                out += ". valid choices are: %s." % ','.join(['\`%s\`' % s for s
                                                              in a.choices])
            if a.default:
                out += ". defaults to: '%s'." % a.default
            out += '\n\n'
        elif len(parser._positionals._group_actions) > 1:
            out += "positional arguments\n"
            for index, a in enumerate(parser._positionals._group_actions):
                out += "\t:%s: %s" % (index, a.help)
                if a.choices:
                    out += ". valid choices are: %s." % ','.join(['\`%s\`' % s for s
                                                                  in a.choices])
                if a.default:
                    out += ". defaults to: '%s'." % a.default
                out += '\n'
            out += '\n\n'

        if parser._optionals._group_actions:
            out += "optional arguments\n"
        for a in parser._optionals._group_actions:
            switches = [s.replace('--','---') for s in a.option_strings]
            out += "\t:%s: %s" % (', '.join(switches), a.help)
            if a.choices:
                out += ". Valid choices are: %s" % ','.join(['\`%s\`' % s for s
                                                              in a.choices])
            if a.default:
                out += " (Defaults to: '%s')" % a.default
            out += '.\n'
        out += '\n'

        # epilog
        #out += formatter.add_text(parser.epilog)

        return out

def get_mode_docs():
    docs = {}
    b = alot.buffers.Buffer
    for entry in alot.buffers.__dict__.values():
        if isinstance(entry, type):
            if issubclass(entry, b) and not entry == b:
                docs[entry.modename] = entry.__doc__.strip()
    return docs


if __name__ == "__main__":

    modes = []
    for mode, modecommands in COMMANDS.items():
        modefilename = mode+'.rst'
        modefile = open(os.path.join(HERE, 'usage', 'modes', modefilename), 'w')
        modefile.write('%s\n%s\n' % (mode, '-' * len(mode)))
        if mode != 'global':
            modes.append(mode)
            modefile.write('The following commands are available in %s mode\n\n' % mode)
        else:
            modefile.write('The following commands are available globally\n\n')
        for cmdstring,struct in modecommands.items():
            cls, parser, forced_args = struct
            modefile.write(rstify_parser(parser))
        modefile.close()
    indexfile = open(os.path.join(HERE, 'usage', 'commands.rst'), 'w')

    mode_docstrings = get_mode_docs()
    tbl = ':doc:`modes/global`\n'
    tbl += (' ' * 4) + 'globally available commands\n'
    for m in modes:
        tbl += ':doc:`modes/%s`\n' % m
        tbl += (' ' * 4) + mode_docstrings[m] + '\n'

    includes = '\n'.join([':doc:`modes/%s`' % m for m in modes])
    indexfile.write('Commands\n========\n\n')
    indexfile.write('\n\n')
    indexfile.write(tbl)
    indexfile.close()
