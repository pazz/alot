import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))

from alot.commands import *
from alot.commands import COMMANDS
import alot.buffers
from alot.utils.argparse import BooleanAction


NOTE = ".. CAUTION: THIS FILE IS AUTO-GENERATED!\n\n\n"


class HF(argparse.HelpFormatter):
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
    parser.formatter_class = HF

    formatter = parser._get_formatter()
    out = ""

    # usage
    usage = formatter._format_usage(None, parser._actions,
                                    parser._mutually_exclusive_groups,
                                    '').strip()
    usage = usage.replace('--', '---')

    # section header
    out += '.. describe:: %s\n\n' % parser.prog

    # description
    out += ' ' * 4 + parser.description
    out += '\n\n'

    if len(parser._positionals._group_actions) == 1:
        out += "    argument\n"
        a = parser._positionals._group_actions[0]
        out += ' '*8 + str(parser._positionals._group_actions[0].help)
        if a.choices:
            out += "; valid choices are: %s" % ','.join(['\'%s\'' % s for s
                                                         in a.choices])
        if a.default:
            out += " (defaults to: '%s')" % a.default
        out += '\n\n'
    elif len(parser._positionals._group_actions) > 1:
        out += "    positional arguments\n"
        for index, a in enumerate(parser._positionals._group_actions):
            out += "        %s: %s" % (index, a.help)
            if a.choices:
                out += "; valid choices are: %s" % ','.join(
                    ['\'%s\'' % s for s in a.choices])
            if a.default:
                out += " (defaults to: '%s')" % a.default
            out += '\n'
        out += '\n\n'

    if parser._optionals._group_actions:
        out += "    optional arguments\n"
    for a in parser._optionals._group_actions:
        switches = [s.replace('--', '---') for s in a.option_strings]
        out += "        :%s: %s" % (', '.join(switches), a.help)
        if a.choices and not isinstance(a, BooleanAction):
            out += "; valid choices are: %s" % ','.join(['\'%s\'' % s for s
                                                         in a.choices])
        if a.default:
            out += " (defaults to: '%s')" % a.default
        out += '\n'
    out += '\n'

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
    for mode, modecommands in sorted(COMMANDS.items()):
        path = (HERE / "usage" / "modes" / mode).with_suffix('.rst')
        with path.open("w") as modefile:
            modefile.write(NOTE)
            if mode != 'global':
                modes.append(mode)
                header = 'Commands in \'%s\' mode' % mode
                intro = 'The following commands are available in %s mode:' % mode
            else:
                header = 'Global commands'
                intro = 'The following commands are available globally:'
            modefile.write(header)
            modefile.write('\n%s\n' % ('-' * len(header)))
            modefile.write(intro)
            modefile.write('\n\n')
            for cmdstring, struct in sorted(modecommands.items()):
                cls, parser, forced_args = struct
                labelline = '.. _cmd.%s.%s:\n\n' % (mode, cmdstring.replace('_',
                                                                            '-'))
                modefile.write(labelline)
                modefile.write(rstify_parser(parser))
