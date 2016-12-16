#!/usr/bin/python
"""
 THEME CONVERTER
 this script converts your custom alot theme files from the v.3.1 syntax
 to the current format.

     >>> theme_convert.py -o themefile.new themefile.old
"""

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
        if path[0] in cfg:
            scfg = cfg[path[0]]
            sp = path[1:]
            return get_leaf_value(scfg, sp, fallback)
        else:
            return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='update alot theme files')
    parser.add_argument('themefile', type=argparse.FileType('r'),
                        help='theme file to convert')
    parser.add_argument('-o', type=argparse.FileType('w'), dest='out',
                        help='destination', default=sys.stdout)
    args = parser.parse_args()

    old = ConfigObj(args.themefile)
    new = ConfigObj()
    out = args.out

    def lookup(path):
        values = []
        for c in ['1', '16', '256']:
            values.append(get_leaf_value(old, [c] + path + ['fg']) or 'default')
            values.append(get_leaf_value(old, [c] + path + ['bg']) or 'default')
        return values

    for bmode in ['global', 'help', 'envelope']:
        new[bmode] = {}
        #out.write('[%s]\n' % bmode)
        for themable in old['16'][bmode].sections:
            new[bmode][themable] = lookup([bmode, themable])
            #out.write('    %s = %s\n' % (themable, lookup([bmode, themable])))

    # BUFFERLIST
    new['bufferlist'] = {}
    new['bufferlist']['line_even'] = lookup(['bufferlist','results_even'])
    new['bufferlist']['line_odd'] = lookup(['bufferlist','results_odd'])
    new['bufferlist']['line_focus'] = lookup(['bufferlist','focus'])

    # TAGLIST
    new['taglist'] = {}
    new['taglist']['line_even'] = lookup(['bufferlist','results_even'])
    new['taglist']['line_odd'] = lookup(['bufferlist','results_odd'])
    new['taglist']['line_focus'] = lookup(['bufferlist','focus'])

    # SEARCH
    new['search'] = {}

    new['search']['threadline'] = {}
    new['search']['threadline']['normal'] = lookup(['search', 'thread'])
    new['search']['threadline']['focus'] = lookup(['search', 'thread_focus'])
    new['search']['threadline']['parts'] = ['date','mailcount','tags','authors','subject']

    new['search']['threadline']['date'] = {}
    new['search']['threadline']['date']['normal'] = lookup(['search', 'thread_date'])
    new['search']['threadline']['date']['focus'] = lookup(['search', 'thread_date_focus'])

    new['search']['threadline']['mailcount'] = {}
    new['search']['threadline']['mailcount']['normal'] = lookup(['search', 'thread_mailcount'])
    new['search']['threadline']['mailcount']['focus'] = lookup(['search', 'thread_mailcount_focus'])

    new['search']['threadline']['tags'] = {}
    new['search']['threadline']['tags']['normal'] = lookup(['search', 'thread_tags'])
    new['search']['threadline']['tags']['focus'] = lookup(['search', 'thread_tags_focus'])

    new['search']['threadline']['authors'] = {}
    new['search']['threadline']['authors']['normal'] = lookup(['search', 'thread_authors'])
    new['search']['threadline']['authors']['focus'] = lookup(['search', 'thread_authors_focus'])

    new['search']['threadline']['subject'] = {}
    new['search']['threadline']['subject']['normal'] = lookup(['search', 'thread_subject'])
    new['search']['threadline']['subject']['focus'] = lookup(['search', 'thread_subject_focus'])

    new['search']['threadline']['content'] = {}
    new['search']['threadline']['content']['normal'] = lookup(['search', 'thread_content'])
    new['search']['threadline']['content']['focus'] = lookup(['search', 'thread_content_focus'])

    # THREAD
    new['thread'] = {}
    new['thread']['attachment'] = lookup(['thread','attachment'])
    new['thread']['attachment_focus'] = lookup(['thread','attachment_focus'])
    new['thread']['body'] = lookup(['thread','body'])
    new['thread']['arrow_heads'] = lookup(['thread','body'])
    new['thread']['arrow_bars'] = lookup(['thread','body'])
    new['thread']['header'] = lookup(['thread','header'])
    new['thread']['header_key'] = lookup(['thread','header_key'])
    new['thread']['header_value'] = lookup(['thread','header_value'])
    new['thread']['summary'] = {}
    new['thread']['summary']['even'] = lookup(['thread','summary_even'])
    new['thread']['summary']['odd'] = lookup(['thread','summary_odd'])
    new['thread']['summary']['focus'] = lookup(['thread','summary_focus'])

    # write out
    new.write(out)
