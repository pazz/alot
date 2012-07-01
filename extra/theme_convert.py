#!/usr/bin/python

from configobj import ConfigObj
import argparse
import sys


def get_leaf_value(cfg, path, fallback=''):
    if len(path) == 1:
        if isinstance(cfg, ConfigObj):
            if path[0] not in cfg.scalars:
                return fallback
            else:
                return cfg[path[0]]
        else:
            if path[0] not in cfg:
                return fallback
            else:
                return cfg[path[0]]
    else:
        scfg = cfg[path[0]]
        sp = path[1:]
        return get_leaf_value(scfg, sp, fallback)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='update alot theme files')
    parser.add_argument('themefile', type=argparse.FileType('r'),
                        help='theme file to convert')
    parser.add_argument('-o', type=argparse.FileType('w'), dest='out',
                        help='destination', default=sys.stdout)
    args = parser.parse_args()

    old = ConfigObj(args.themefile)
    out = args.out

    def lookup(path):
        values = []
        for c in ['1', '16', '256']:
            values.append(get_leaf_value(old, [c] + path + ['fg']))
            values.append(get_leaf_value(old, [c] + path + ['bg']))
        values = map(lambda s: '\'' + s + '\'', values)
        return ','.join(values)

    for bmode in ['global', 'help', 'bufferlist', 'thread', 'envelope']:
        out.write('[%s]\n' % bmode)
        for themable in old['1'][bmode].sections:
            out.write('    %s = %s\n' % (themable, lookup([bmode, themable])))

    out.write('[search]\n')
    out.write('    [[threadline]]\n')

    out.write(' ' * 8 + 'normal = %s\n' % lookup(['search', 'thread']))
    out.write(' ' * 8 + 'focus = %s\n' % lookup(['search', 'thread_focus']))
    out.write(' ' * 8 + 'order = date,mailcount,tags,authors,subject\n')

    out.write(' ' * 8 + '[[date]]\n')
    out.write(' ' * 12 + 'normal = %s\n' % lookup(['search', 'thread_date']))
    out.write(' ' * 12 + 'focus = %s\n' % lookup(['search', 'thread_date_focus']))
    out.write(' ' * 8 + '[[mailcount]]\n')
    out.write(' ' * 12 + 'normal = %s\n' % lookup(['search', 'thread_mailcount']))
    out.write(' ' * 12 + 'focus = %s\n' % lookup(['search', 'thread_mailcount_focus']))
    out.write(' ' * 8 + '[[tags]]\n')
    out.write(' ' * 12 + 'normal = %s\n' % lookup(['search', 'thread_tags']))
    out.write(' ' * 12 + 'focus = %s\n' % lookup(['search', 'thread_tags_focus']))
    out.write(' ' * 8 + '[[authors]]\n')
    out.write(' ' * 12 + 'normal = %s\n' % lookup(['search', 'thread_authors']))
    out.write(' ' * 12 + 'focus = %s\n' % lookup(['search', 'thread_authors_focus']))
    out.write(' ' * 8 + '[[subject]]\n')
    out.write(' ' * 12 + 'normal = %s\n' % lookup(['search', 'thread_subject']))
    out.write(' ' * 12 + 'focus = %s\n' % lookup(['search', 'thread_subject_focus']))
    out.write(' ' * 8 + '[[content]]\n')
    out.write(' ' * 12 + 'normal = %s\n' % lookup(['search', 'thread_content']))
    out.write(' ' * 12 + 'focus = %s\n' % lookup(['search', 'thread_content_focus']))
