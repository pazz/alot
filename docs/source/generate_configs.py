import sys
import os
HERE = os.path.dirname(__file__)
sys.path.append(os.path.join(HERE, '..', '..', '..'))
from alot.commands import COMMANDS
from configobj import ConfigObj
import re

def rewrite_scalarcomments(config, path):
    file = open(path, 'w')
    for entry in config.scalars:
        description = '\n.. describe:: %s\n\n' % entry
        comments = [config.inline_comments[entry]] + config.comments[entry]
        for c in comments:
            if c:
                description += ' '*4 + re.sub('^\s*#\s*', '', c) + '\n'
        file.write(description)
    file.close()

if __name__ == "__main__":
    specpath = os.path.join(HERE, '..','..', 'alot', 'defaults', 'alot.rc.spec')
    config = ConfigObj(specpath)

    alotrc_table_file = os.path.join(HERE, 'configuration', 'alotrc_table.rst')
    rewrite_scalarcomments(config, alotrc_table_file)

    rewrite_scalarcomments(config['accounts']['__many__'],
                           os.path.join(HERE, 'configuration',
                                        'accounts_table.rst'))
