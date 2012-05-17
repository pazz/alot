import sys
import os
HERE = os.path.dirname(__file__)
sys.path.append(os.path.join(HERE, '..', '..', '..'))
from alot.commands import COMMANDS
from configobj import ConfigObj
from validate import Validator
import re
NOTE = """..
    CAUTION: THIS FILE IS AUTO-GENERATED
    from the inline comments of specfile %s.

    If you want to change its content make your changes
    to that spec to ensure they woun't be overwritten later.
"""
def rewrite_entries(config, path, specpath, sec=None, sort=False):
    file = open(path, 'w')
    file.write(NOTE % specpath)

    if sec == None:
        sec = config
    if sort:
        sec.scalars.sort()
    for entry in sec.scalars:
        v = Validator()
        #config.validate(v)
        #print config[entry]
        #etype = re.sub('\(.*\)','', config[entry])
        ##if etype == 'option':
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
                description += ' '*4 + re.sub('^\s*#', '', c) + '\n'
        if etype == 'option':
            description += '\n    :type: option, one of %s\n' % eargs
        else:
            if etype == 'force_list':
                etype = 'string list'
            description += '\n    :type: %s\n' % etype

        if default != None:
            if etype in ['string', 'string_list', 'gpg_key_hint'] and default != 'None':
                description += '    :default: `%s`\n\n' % (default)
            else:
                description += '    :default: %s\n\n' % (default)
        file.write(description)
    file.close()

if __name__ == "__main__":
    specpath = os.path.join(HERE, '..','..', 'alot', 'defaults', 'alot.rc.spec')
    config = ConfigObj(None, configspec=specpath, stringify=False, list_values=False)
    config.validate(Validator())

    alotrc_table_file = os.path.join(HERE, 'configuration', 'alotrc_table.rst')
    rewrite_entries(config.configspec, alotrc_table_file, 'defaults/alot.rc.spec', sort=True)

    rewrite_entries(config, os.path.join(HERE, 'configuration', 'accounts_table.rst'),
                    'defaults/alot.rc.spec',
                    sec=config.configspec['accounts']['__many__'])
