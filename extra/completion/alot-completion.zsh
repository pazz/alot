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
  if (( CURRENT > 2 )) ; then
    local cmd=${words[2]}
    curcontext="${curcontext%:*:*}:alot-$cmd"
    (( CURRENT-- ))
    shift words
    _call_function ret _alot_$cmd
    return ret
  else
    _alot_subcommands
  fi
}

_alot "$@"

# vim: set sw=2 sts=2 ts=2 et ft=zsh :
