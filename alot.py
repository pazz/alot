#!/usr/bin/python
import argparse
import logging

from alot.db import DBManager
from alot.ui import UI


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', dest='read_only',
                        action='store_true',
                        help='open db in read only mode')
    parser.add_argument('-m', dest='mouse',
                        action='store_true',
                        default=False,
                        help='use mouse input')
    parser.add_argument('-p', dest='db_path',
                        help='path to notmuch index')
    parser.add_argument('-d', dest='debug_level',
                        default='info',
                        help='one of DEBUG,INFO,WARNING,ERROR')
    parser.add_argument('-l', dest='logfile',
                        default='debug.log',
                        help='logfile')
    parser.add_argument('query', nargs='?',
                        default='tag:inbox AND NOT tag:killed',
                        help='initial searchstring')
    return parser.parse_args()


def main():
    args = parse_args()
    dbman = DBManager(path=args.db_path, ro=args.read_only)
    numeric_level = getattr(logging, args.debug_level.upper(), None)
    logging.basicConfig(level=numeric_level, filename=args.logfile)
    logger = logging.getLogger()
    ui = UI(db=dbman,
            log=logger,
            handle_mouse=args.mouse,
            search=args.query)

if __name__ == "__main__":
    main()
