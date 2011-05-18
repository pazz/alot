#!/usr/bin/python
import argparse
import logging
from ng.db import DBManager
from ng.ui import UI

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-ro','--read-only', action='store_true', help='open db in read only mode')
    parser.add_argument('--dbpath', help='path to notmuch index')
    parser.add_argument('-d','--debug-level', default='info', help='one of DEBUG,INFO,WARNING,ERROR')
    parser.add_argument('-l','--logfile', help='logfile', default='ng.log')
    args = parser.parse_args()

    dbman = DBManager(path=args.dbpath,ro=args.read_only)
    numeric_level = getattr(logging, args.debug_level.upper(), None)
    logging.basicConfig(level=numeric_level, filename=args.logfile)
    logger = logging.getLogger()
    ui = UI(db=dbman,log=logger)
