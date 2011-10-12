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

Why are searches with large result sets slower than in the Emacs mode?
-----------------------------------------------------
Short answer: The Emacs mode cheats: it makes use of the editors ability to
asynchronously handle buffers, so you can work on the initial prefix although it takes
ages to fill the rest. Due to the nature of notmuch's python bindings,
*alot* needs to copy enough information to reproduce the results to a more durable datastructure
before it can display it.

The technical answer:
*alot* queries notmuch and copies the thread ids from the result set to a list,
which is then used to dynamically load all the info once a thread gets displayed.
This is significantly faster than instanciating alot.db.thread objects for all
results directly, but of course, copying a large list costs.
The problem is that the iterator that the notmuch api returns _must_
be read at once, otherwise it may get outdated.
One might think "so what? Then I get old results" No: if you read from an
outdated notmuch iterator, it throws an exception and dies.

If you'd like to have a look how it works currently, look at `walker.py`
and `buffer.SearchBuffer`.
I have played around with dynamically re-creating these iterators if they fail.
But then you need to synchronise with all that has been read so far. Particularly popping
already read threads from the iterator. Its ugly.

One better way to implement this might be to somehow outsource
the query into a thread (as Emacs does) and communicate a prefix of the result
to the display using thread-voodoo.

I want feature X!
-----------------
Me too! Feel free to file a new (or comment on an existing) [issue][issue] if you don't
want/have the time/know how to implement it yourself. Be verbose as to
how it should look or work when its finished and give it some thought how you
think we should implement it. We'll discuss it from there.


[issue]: https://github.com/pazz/alot/issues
[inittag]: http://notmuchmail.org/initial_tagging/
[notmuch]: http://notmuchmail.org
[toolkit]: http://excess.org/urwid/
[python]: http://www.python.org/
