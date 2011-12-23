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
how it should look or work when its finished and give it some thought how you
think we should implement it. We'll discuss it from there.

Why are the default key bindings so counter-intuitive?
---------------------------------------------------
Be aware that the bindings for all modes are fully configurable (see the CUSTOMIZE.md).
That said, I choose the bindings to be natural for me. I use vim and [pentadactyl][pd] a lot.
However, I'd be interested in discussing the defaults. If you think
your bindings are more intuitive or better suited as defaults for some reason,
don't hesitate to send me your config. The same holds for the theme settings you use.
Tell me. Let's improve the defaults.

How do I do contacts completion?
--------------------------------
In each `account` section you can specify a `abook_command` that
is considered the address book of that account and will be used
for address completion where appropriate.

This shell command will be called with the search prefix as only argument.
Its output is searched for email-name pairs using the regular expression given as `abook_regexp`,
which must include named groups "email" and "name" to match the email address and realname parts
respectively. See below for an example that uses [abook][abook]:

```
[account YOURACCOUNT]
realname = ...
address = ...
abook_command = abook --mutt-query
abook_regexp = (?P<email>.+?@.+?)\s+(?P<name>.+)
```

See [here][alookup] for alternative lookup commands. The few others I have tested so far are:

 * [goobook][gbook] for cached google contacts lookups:

   ```
   abook_command = goobook query
   abook_regexp = (?P<email>.+?@.+?)\s\s+(?P<name>.+)\s\s+.+
   ```
 
 * [nottoomuch-addresses][nottoomuch]:

   ```
   abook_command = nottoomuch-addresses.sh
   abook_regexp = \"(?P<name>.+)\"\s*<(?P<email>.*.+?@.+?)>
   ```

Don't hesitate to send me your custom `abook_regexp` values to list them here.


[issue]: https://github.com/pazz/alot/issues
[inittag]: http://notmuchmail.org/initial_tagging/
[notmuch]: http://notmuchmail.org
[toolkit]: http://excess.org/urwid/
[python]: http://www.python.org/
[pd]: http://dactyl.sourceforge.net/pentadactyl/
[abook]: http://abook.sourceforge.net/
[gbook]: http://code.google.com/p/goobook/
[nottoomuch]: http://www.iki.fi/too/nottoomuch/nottoomuch-addresses/
[alookup]: http://notmuchmail.org/emacstips/#index11h2
