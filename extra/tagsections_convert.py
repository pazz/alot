#!/usr/bin/python
"""
 CONFIG CONVERTER
 this script converts your custom tag string section from the v.3.1 syntax
 to the current format.

     >>> tagsections_convert.py -o config.new config.old

 will convert your whole alot config safely to the new format.
"""

from configobj import ConfigObj
import argparse
import sys
import re


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
    parser.add_argument('configfile', type=argparse.FileType('r'),
                        help='theme file to convert')
    parser.add_argument('-o', type=argparse.FileType('w'), dest='out',
                        help='destination', default=sys.stdout)
    args = parser.parse_args()

    cfg = ConfigObj(args.configfile)
    out = args.out
    print args

    def is_256(att):
        r = r'(g\d{1,3}(?!\d))|(#[0-9A-Fa-f]{3}(?![0-9A-Fa-f]))'
        return re.search(r, att)

    if 'tags' in cfg:
        for tag in cfg['tags'].sections:
            sec = cfg['tags'][tag]
            att = [''] * 6

            if 'fg' in sec:
                fg = sec['fg']
                if not is_256(fg):
                    att[2] = fg
                att[4] = fg
                del sec['fg']

            if 'bg' in sec:
                bg = sec['bg']
                if not is_256(bg):
                    att[3] = bg
                att[5] = bg
                del sec['bg']
            sec['normal'] = att

            if sec.get('hidden'):
                sec['translated'] = ''
    cfg.write(out)
