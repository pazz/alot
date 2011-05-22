#!/usr/bin/python
import argparse
import logging

from ng.db import DBManager
from ng.ui import UI


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--read-only', action='store_true',
                        help='open db in read only mode')
    parser.add_argument('-m', '--handle-mouse', action='store_true',
                        default=False, help='use mouse input')
    parser.add_argument('--dbpath', help='path to notmuch index')
    parser.add_argument('-d', '--debug-level', default='info',
                        help='one of DEBUG,INFO,WARNING,ERROR')
    parser.add_argument('-l', '--logfile', default='debug.log',
                        help='logfile')
    return parser.parse_args()


def main():
    args = parse_args()
    dbman = DBManager(path=args.dbpath, ro=args.read_only)
    numeric_level = getattr(logging, args.debug_level.upper(), None)
    logging.basicConfig(level=numeric_level, filename=args.logfile)
    logger = logging.getLogger()
    ui = UI(db=dbman,
            log=logger,
            handle_mouse=args.handle_mouse)

if __name__ == "__main__":
    main()
