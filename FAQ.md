FAQ
===
What is all this about?
-----------------------
[*notmuch*][notmuch] is an email indexer that allows you to search through you mails,
making traditional folder based access to emails obsolete.
It is (email)thread based and makes extensive use of the tagging metaphor.
notmuch provides a C-library and bindings for several other languages and a CLI tool.
Additionally, there are several interfaces that let you interact with your index
and provide additional MUA functionality.

*alot* is such an interface. It lives in your terminal and tries hard to look
and feel like a MUA. It is intended as a notmuch based MUA for people
unwilling to use their editor as a mailclient.
  
Why reinvent the wheel? Why not extend an existing MUA to work nicely with notmuch?
-----------------------------------------------------------------------------------
*alot* makes use of existing solutions where possible: 
It does not fetch, send or edit mails; it lets *notmuch* handle your mailindex and uses
a [toolkit][toolkit] to render its display. You are responsible for [automatic initial tagging][inittag].

This said, there are few CLI MUAs that could be easily and naturally adapted to using notmuch.
Rebuilding an interface from scratch using [friendly and extensible tools][python] seemed easier
and more promising.

What's with the snotty name?
----------------------------
It's not meant to be presumptuous. I like the dichotomy;
I like to picture the look on someone's face who reads the X-MAILER flag
"notmuch/alot"; I like cookies; I like this comic strip:
http://hyperboleandahalf.blogspot.com/2010/04/alot-is-better-than-you-at-everything.html

I want feature X!
-----------------
Me too! Feel free to file a new (or comment on an existing) [issue][issue] if you don't
want/have the time/know how to implement it yourself. Be verbose as to
how it should look or work when it's finished and give it some thought how you
think we should implement it. We'll discuss it from there.

Why are the default key bindings so counter-intuitive?
------------------------------------------------------
Be aware that the bindings for all modes are fully configurable (see the CUSTOMIZE.md).
That said, I choose the bindings to be natural for me. I use vim and [pentadactyl][pd] a lot.
However, I'd be interested in discussing the defaults. If you think
your bindings are more intuitive or better suited as defaults for some reason,
don't hesitate to send me your config. The same holds for the theme settings you use.
Tell me. Let's improve the defaults.

Why are you $this not $that way?
--------------------------------
Lazyness and Ignorance: In most cases I simply did not or still don't know a better solution.
I try to outsource as much as I can to well established libraries and be it only to avoid
having to read rfc's. But there are lots 
of tasks I implemented myself, possibly overlooking a ready made and available solution.
Twisted is such a feature-rich but gray area in my mind for example.
If you think you know how to improve the current implementation let me know!

The few exceptions to above stated rule are the following:
* CLI option parsing is done using twisted.usage.Options, and not (as e.g. in-app command parsing)
  via argparse. The reason is that argparse does not yet offer optional subcommands.
* The modules cmd and cmd2, that handle all sorts of convenience around command objects
  hate urwid: They are painfully strongly coupled to user in/output via stdin and out.
* `notmuch reply` is not used to format reply messages because 1. it is not offered by
  notmuch's library but is a feature of the CLI. This means we would have to call the notmuch
  binary, something that is avoided where possible. 2. As there is no `notmuch forward` equivalent,
  this (very similar) functionality would have to be re-implemented anyway.



[issue]: https://github.com/pazz/alot/issues
[inittag]: http://notmuchmail.org/initial_tagging/
[notmuch]: http://notmuchmail.org
[toolkit]: http://excess.org/urwid/
[python]: http://www.python.org/
[pd]: http://dactyl.sourceforge.net/pentadactyl/
