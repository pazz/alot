#compdef alot

# ZSH completion for `alot`, Shamelessly copied from notmuch's zsh completion file
# Copyright © 2009 Ingmar Vanhassel <ingmar@exherbo.org>
# Copyright © 2012 Patrick Totzke <patricktotzke@gmail.com>

_alot_subcommands()
{
  local -a alot_subcommands
  alot_subcommands=(
    'search:search for messages matching the search terms, display matching threads as results'
    'compose:compose a new message'
  )

  _describe -t command 'command' alot_subcommands
}

_alot_search()
{
  _arguments -s : \
    '--sort=[sort results]:sorting:((newest_first\:"reverse chronological order" oldest_first\:"chronological order" message_id\:"lexicographically by Message Id"))'
}

_alot_compose()
{
  _arguments -s : \
    '--omit_signature[do not add signature]' \
    '--sender=[From header]' \
    '--subject=[Subject header]' \
    '--cc=[Carbon Copy header]' \
    '--bcc=[Blind Carbon Copy header]' \
    '--template=[template file to use]' \
    '--attach=[Attach files]:attach:_files -/'\
}

_alot()
{
  local state
  local ret=1
  # Complete global options.  Set $state to "command" or "options" in order to
  # do further completion.
  _arguments \
    '(- *)--help[show the help message]' \
    '(- *)--version[show version information]' \
    '(--help --version -r --read-only)'-{r,-read-only}'[open db in read only mode]' \
    '(--help --version -c --config)'-{c,-config}'[specify an alternative config file]:alot config file:_files' \
    '(--help --version -n --notmuch-config)'-{n,-notmuch-config}'[specify an alternative notmuch config file]:notmuch config file:_files' \
    '(--help --version -C --colour-mode)'-{C,-colour-mode}'[terminal colour mode]:colour mode:(1 16 256)' \
    '(--help --version -p --mailindex-path)'-{p,-mailindex-path}'[path to notmuch index]:directory:_directories' \
    '(--help --version -d --debug-level)'-{d,-debug-level}'[set the log level]:debug level:(debug info warning error)' \
    '(--help --version -l --logfile)'-{l,-logfile}'[specify the logfile (default: /dev/null)]:log file:_files' \
    ': :->command' \
    '*:: :->options' \
  && ret=0

  case $state in
    command)
      _alot_subcommands
      ;;
    options)
      # Call the specific completion function for the subcommand.
      _call_function ret _alot_$words[1]
      ;;
  esac

  return ret
}

_alot $@

# vim: set sw=2 sts=2 ts=2 et ft=zsh :
