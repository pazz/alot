This is a proposal for a terminal gui for `notmuch mail <http://notmuchmail.org/>`, 
written in python using the `urwid <http://excess.org/urwid/>` toolkit.

You can find some old screenshots in `data/alot*png`,
the files `INSTALL` and `USAGE` contain instructions on how to set it up,
use and customize. These files are nicely rendered in the github
`wiki <https://github.com/pazz/alot/wiki>`.
The API docs for the current master branch are `here <http://pazz.github.com/alot/>`,
the `docs` directory contains their sources.

Do comment on the code or file issues! I'm curious what you think of it.
Talk to me in #notmuch@Freenode.

Current features include:
-------------------------
 * spawn terminals for asynchronous editing of mails
 * theming, optionally in monochromatic, 16 or 256 colours
 * tag specific theming and tagstring translation
 * a hook system to inject one's own python code
 * python shell for introspection
 * forward/reply/group-reply of emails
 * multiple accounts for sending mails via sendmail
 * tab completion for commands and querystrings
 * priorizable notification popups
 * database manager that manages a write queue to the notmuch index
 * user configurable keyboard maps

Soonish to be addressed non-features:
-------------------------------------
 * encryption/decryption for messages
 * search for strings in displayed buffer
 * print command
 * folding for message parts
 * undo for commands
 * addressbook integration
