Configfile Layout
------------------
Just like offlineimap or notmuch itself, alot reads a config file in the "INI" syntax:
It consists of some sections whose names are given in square brackets, followed by
key-value pairs that use "=" or ":" as separator, ';' and '#' are comment-prefixes.

The default location for the config file is `~/.config/alot/config`.
You can find a complete example config with the default values and their decriptions in
`alot/defaults/alot.rc`.

Note that since ":" is a separator for key-value pairs you need to use "colon" to bind
commands to ":".

Here is a key for the interpreted sections:

    [general]
        global settings: set your editor etc
    
    [account X]
        defines properties of account X: (see below)
    
    [X-maps]
        defines keymaps for mode X. possible modes are:
        envelope, search, thread, taglist, bufferlist and global.
        global-maps are valid in all modes.
    
    [tag-translate]
        defines a map from tagnames to strings that is used when
        displaying tags. utf-8 symbols welcome.
    
    [Xc-theme]
        define colour palette for colour mode. X is in {1, 16, 256}.

All configs are optional, but if you want to send mails you need to
specify at least one account section.


Account Sections
----------------
A sample gmail section looks like this (provided you have configured msmtp accordingly):

    [account gmail]
    realname = Patrick Totzke
    address = patricktotzke@gmail.com
    aliases = patricktotzke@googlemail.com
    sendmail_command = msmtp --account=gmail -t

Here's a full list of the interpreted keywords in account sections:

    # used to format the (proposed) From-header in outgoing mails
    realname = your name
    address = this accounts email address

    # used to clear your addresses/ match account when formating replies 
    aliases = foobar@myuni.uk;f.bar@myuni.uk;f.b100@students.myuni.uk
    
    # how to send mails
    sendmail_command = command, defaults to 'sendmail'

    # where to store outgoing mail
    sent_box = maildir:///home/you/mail//Sent

    # file to append before sending
    signature = ~/your_vcard_for_this_account.vcs
    # signature file's name as it appears in outgoing mails
    signature_filename = you.vcs

    # command to lookup contacts
    abook_command = abook --mutt-query
    abook_regexp = regexp to match name & address in abook_commands output.

Caution: Sending mails is only supported via sendmail for now. If you want
to use a sendmail command different from `sendmail`, specify it as `sendmail_command`.

`send_box` specifies the mailbox where you want outgoing mails to be stored
after successfully sending them. You can use mbox, maildir, mh, babyl and mmdf
in the protocol part of the url.

The file specified by `signature` is attached to all outgoing mails from this account, optionally
renamed to `signature_filename`.

If you specified `abook_command`, it will be used for tab completion in queries (to/from)
and in message composition. The command will be called with your prefix as only argument
and its output is searched for name-email pairs. The regular expression used here
defaults to `(?P<email>.+?@.+?)\s+(?P<name>.+)`, which makes it work nicely with `abook --mutt-query`.
You can tune this using the `abook_regexp` option (beware Commandparsers escaping semantic!).


Key Bindings
------------
If you want to bind a commandline to a key you can do so by adding the pair to the
`[MODE-maps]` config section, where MODE is the buffer mode you want the binding to hold.
Consider the following lines, which allow you to send mails in envelope buffers using the
combination `control` + `s`:

    [envelope-maps]
    ctrl s = send

Possible MODE strings are:

 * envelope
 * search
 * thread
 * taglist
 * bufferlist
 * global

Bindings defined in section `[global-maps]` are valid in all modes.

Have a look at [the urwid User Input documentation][keys] on how key strings are formated.

[keys]: http://excess.org/urwid/wiki/UserInput


Hooks
-----
Hooks are python callables that live in a module specified by
`hooksfile` in the `[global]` section of your config. Per default this points
to `~/.config/alot/hooks.py`.
For every command X, the callable 'pre_X' will be called before X and 'post_X' afterwards.

When a hook gets called, it receives instances of

 * ui: [`alot.ui.UI`][ui], the main user interface object that can prompt etc.
 * dbm: [`alot.db.DBManager`][db], the applications database manager
 * aman: [`alot.account.AccountManager`][am], can be used to look up account info
 * log: [`logging.Logger`][log], to write to logfile
 * config: [`alot.settings.config`][config], a configparser to access the users config

[ui]: http://alot.readthedocs.org/en/docs/interface.html#alot.ui.UI
[db]: http://alot.readthedocs.org/en/docs/database.html#alot.db.DBManager
[am]: http://alot.readthedocs.org/en/docs/accounts.html#alot.account.AccountManager
[log]: http://docs.python.org/py3k/library/logging.html#logging.Logger
[config]: http://alot.readthedocs.org/en/docs/settings.html#alot.settings.AlotConfigParser

An autogenerated API doc for these can be found at http://alot.rtfd.org ,
the sphinx sources live in the `docs` folder.
As an example, consider this pre-hook for the exit command,
that logs a personalized goodby message:

```python
def pre_exit(aman=None, log=None, **rest):
    accounts = aman.get_accounts()
    if accounts:
        log.info('goodbye, %s!' % accounts[0].realname)
    else:
        log.info('goodbye!')
```

Apart from command pre and posthooks, the following hooks will be interpreted:

 * `reply_prefix(realname, address, timestamp, **kwargs)`
   Is used to reformat the first indented line in a reply message.
   Should return a string and defaults to 'Quoting %s (%s)\n' % (realname, timestamp)
 * `forward_prefix(realname, address, timestamp, **kwargs)`
   Is used to reformat the first indented line in a inline forwarded message.
   Returns a string and defaults to 'Forwarded message from %s (%s)\n' % (realname, timestamp)
 * `pre_edit_translate(bodytext, **kwargs)`
   can be used to manipulate a messages bodytext before the editor is called.
   Receives and returns a string.
 * `post_edit_translate(bodytext, **kwargs)`
   can be used to manipulate a messages bodytext after the editor is called
   Receives and returns a string.


Colours
-------
You can change the colour settings in the section `[Xc-theme]`, where X is the
colour mode you use. This defaults to 256, but 16 and 1 are also possible.
The colourmode can be changed in the globals section or given as a commandline
parameter (-C).
The keys in this section should be self explanatory. In 16c and 256c modes you can define Y_fg and
Y_bg for the foreground and background of each keyword Y. These can define colourcodes and flags
like `underline` or `bold`, comma separated if you want more than one. See urwids doc on Attributes:
http://excess.org/urwid/reference.html#AttrSpec
Urwid privides a neat script that makes choosing colours easy, which can be found here:
http://excess.org/urwid/browser/palette_test.py

See the contents of `alot/defaults/alot.rc` for a complete list of widgets that can be themed.


Custom Tagstring formating
--------------------------
Keywords in the theme sections that start with "tag_" will be used to display specific tags.
For instance, you can use the following to always display the "todo" tag in white on red,
when in 256c-mode.

    [256c-theme]
    tag_todo_bg = #d66
    tag_todo_fg = white

You can translate tag strings before displaying them using the [tag-translate] section.
A key=value statement in this section is interpreted as:
Always display the tag `key` as string `value`. Utf-8 symbols are welcome here.
See e.g. http://panmental.de/symbols/info.htm
I personally display my maildir flags like this:

    [tag-translate]
    flagged = ⚑
    unread = ✉
    replied = ⇄
