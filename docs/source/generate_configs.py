import sys
import os
import re

from configobj import ConfigObj
from validate import Validator

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..', '..'))

from alot.commands import COMMANDS


NOTE = """
.. CAUTION: THIS FILE IS AUTO-GENERATED
    from the inline comments of specfile %s.

    If you want to change its content make your changes
    to that spec to ensure they woun't be overwritten later.
"""


def rewrite_entries(config, path, specpath, sec=None):
    file = open(path, 'w')
    file.write(NOTE % specpath)

    if sec is None:
        sec = config
    for entry in sorted(sec.scalars):
        v = Validator()
        etype, eargs, ekwargs, default = v._parse_check(sec[entry])
        if default is not None:
            default = config._quote(default)

        if etype == 'gpg_key_hint':
            etype = 'string'
        description = '\n.. _%s:\n' % entry.replace('_', '-')
        description += '\n.. describe:: %s\n\n' % entry
        comments = [sec.inline_comments[entry]] + sec.comments[entry]
        for c in comments:
            if c:
                description += ' ' * 4 + re.sub(r'^\s*#', '', c)
                description = description.rstrip(' ') + '\n'
        if etype == 'option':
            description += '\n    :type: option, one of %s\n' % eargs
        else:
            if etype == 'force_list':
                etype = 'string list'
            description += '\n    :type: %s\n' % etype

        if default is not None:
            default = default.replace('*', '\\*')
            if etype in ['string', 'string_list', 'gpg_key_hint'] and \
                    default != 'None':
                description += '    :default: "%s"\n\n' % (default)
            else:
                description += '    :default: %s\n\n' % (default)
        file.write(description)
    file.close()


if __name__ == "__main__":
    specpath = os.path.join(HERE, '..', '..', 'alot', 'defaults',
                            'alot.rc.spec')
    config = ConfigObj(None, configspec=specpath, stringify=False,
                       list_values=False)
    config.validate(Validator())

    alotrc_table_file = os.path.join(HERE, 'configuration', 'alotrc_table')
    rewrite_entries(config.configspec, alotrc_table_file,
                    'defaults/alot.rc.spec')

    rewrite_entries(config,
                    os.path.join(HERE, 'configuration', 'accounts_table'),
                    'defaults/alot.rc.spec',
                    sec=config.configspec['accounts']['__many__'])
