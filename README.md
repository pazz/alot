Alot is an experimental terminal MUA based on [notmuch mail][notmuch].
It is written in python using the [urwid][urwid] toolkit.

[![Build Status][travis-img]][travis]
[![Code Issues][quantcode-img]][quantcode]

Have a look at the [user manual][docs] for installation notes, advanced usage,
customization and hacking guides.

Do comment on the code or file issues!

Most of the developers hang out in `#alot@freenode`, feel free to ask questions or make suggestions there.

Current features include:
-------------------------
 * modular and command prompt driven interface
 * multiple accounts for sending mails via sendmail
 * spawn terminals for asynchronous editing of mails
 * tab completion and usage help for all commands
 * contacts completion using customizable lookups commands
 * user configurable keyboard maps
 * theming, optionally in 2, 16 or 256 colours
 * tag specific theming and tag string translation
 * (python) hooks to react on events and do custom formatting
 * python shell for introspection
 * forward/reply/group-reply of emails
 * printing/piping of mails and threads
 * notification popups with priorities
 * database manager that manages a write queue to the notmuch index
 * configurable status bar
 * full support for PGP/MIME encryption and signing


Basic Usage
-----------
The arrow keys, `page-up/down`, `j`, `k` and `Space` can be used to move the focus.
`Escape` cancels prompts and `Enter` selects. Hit `:` at any time and type in commands
to the prompt.

The interface shows one buffer at a time, you can use `Tab` and `Shift-Tab` to switch
between them, close the current buffer with `d` and list them all with `;`.

The buffer type or *mode* (displayed at the bottom left) determines which prompt commands
are available. Usage information on any command can be listed by typing `help YOURCOMMAND`
to the prompt; The key bindings for the current mode are listed upon pressing `?`.
See the [manual][docs] for more usage info.

[notmuch]: http://notmuchmail.org/
[urwid]: http://excess.org/urwid/
[docs]: http://alot.rtfd.org
[features]: https://github.com/pazz/alot/issues?labels=feature
[travis]: https://travis-ci.org/pazz/alot
[quantcode]: https://www.quantifiedcode.com/app/project/c5aaa4739c5b4f6eb75eaaf8c01da679

[travis-img]: https://travis-ci.org/pazz/alot.svg?branch=master
[quantcode-img]: https://www.quantifiedcode.com/api/v1/project/c5aaa4739c5b4f6eb75eaaf8c01da679/badge.svg
