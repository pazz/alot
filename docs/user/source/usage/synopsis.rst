.. code-block:: none

    alot [-r] [-c CONFIGFILE] [-n NOTMUCHCONFIGFILE] [-C {1,16,256}] [-p DB_PATH]
         [-d {debug,info,warning,error}] [-l LOGFILE] [--version] [--help]
         [command]

Options

    -r, --read-only                open db in read only mode
    -c, --config=FILENAME          config file (default: ~/.config/alot/config)
    -n, --notmuch-config=FILENAME  notmuch config (default: ~/.notmuch-config)
    -C, --colour-mode=COLOR        terminal colour mode (default: 256). Must be 1, 16 or 256
    -p, --mailindex-path=PATH      path to notmuch index
    -d, --debug-level=LEVEL        debug log (default: info). Must be one of debug,info,warning or error
    -l, --logfile=FILENAME         logfile (default: /dev/null)
    --version                      Display version string and exit
    --help                         Display  help and exit

Commands

    search
        start in a search buffer using the querystring provided as
        parameter. See the SEARCH SYNTAX section of notmuch(1).
    compose
        compose a new message
