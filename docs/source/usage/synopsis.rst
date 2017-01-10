.. code-block:: none

    alot [-r] [-c CONFIGFILE] [-n NOTMUCHCONFIGFILE] [-C {1,16,256}] [-p DB_PATH]
         [-d {debug,info,warning,error}] [-l LOGFILE] [-v] [-h] [command]

Options

    -r, --read-only                open db in read only mode
    -c, --config=FILENAME          config file (default: ~/.config/alot/config)
    -n, --notmuch-config=FILENAME  notmuch config (default: $NOTMUCH_CONFIG or ~/.notmuch-config)
    -C, --colour-mode=COLOUR       terminal colour mode (default: 256). Must be 1, 16 or 256
    -p, --mailindex-path=PATH      path to notmuch index
    -d, --debug-level=LEVEL        debug log (default: info). Must be one of debug,info,warning or error
    -l, --logfile=FILENAME         logfile (default: /dev/null)
    -v, --version                  Display version string and exit
    -h, --help                     Display  help and exit

UNIX Signals
    SIGUSR1
        Refreshes the current buffer. Useful for telling alot to refresh the
        view from a mail downloader e.g. Offlineimap.


Subommands

    search
        start in a search buffer using the querystring provided as
        parameter. See also the SEARCH SYNTAX section of notmuch(1)
        and the output of `alot search --help`.
    compose
        compose a new message
        See the output of `alot compose --help` for more info on parameters.
    pyshell
        start the interactive python shell inside alot
        See the output of `alot pyshell --help` for more info on parameters.
