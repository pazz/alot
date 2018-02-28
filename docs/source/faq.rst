FAQ
***

1. Why reinvent the wheel? Why not extend an existing MUA to work nicely with notmuch?

    alot makes use of existing solutions where possible: It does not fetch, send or edit
    mails; it lets `notmuch <http://notmuchmail.org>`_ handle your mailindex and uses a
    `toolkit <http://excess.org/urwid/>`_ to render its display. You are responsible for
    `automatic initial tagging <http://notmuchmail.org/initial_tagging/>`_.

    This said, there are few CLI MUAs that could be easily and naturally adapted to using notmuch.
    Rebuilding an interface from scratch using `friendly and extensible tools <http://www.python.org/>`_
    seemed easier and more promising.

    Update: see `mutt-kz <https://github.com/karelzak/mutt-kz>`_ for a fork of mutt..

2. What's with the snotty name?

    It's not meant to be presumptuous. I like the dichotomy; I like to picture the look on
    someone's face who reads the :mailheader:`User-Agent` header "notmuch/alot"; I like cookies; I like
    `this comic strip <http://hyperboleandahalf.blogspot.com/2010/04/alot-is-better-than-you-at-everything.html>`_.

3. I want feature X!

    Me too! Feel free to file a new or comment on existing
    `issues <https://github.com/pazz/alot/issues>`_ if you don't want/have the time/know how to
    implement it yourself. Be verbose as to how it should look or work when it's finished and
    give it some thought how you think we should implement it. We'll discuss it from there.

4. Why are the default key bindings so counter-intuitive?

    Be aware that the bindings for all modes are :ref:`fully configurable <config.key_bindings>`.
    That said, I choose the bindings to be natural for me. I use `vim <http://www.vim.org>`_ and
    `pentadactyl <http://dactyl.sourceforge.net/pentadactyl/>`_ a lot.  However, I'd be
    interested in discussing the defaults. If you think your bindings are more intuitive or
    better suited as defaults for some reason, don't hesitate to send me your config. The same
    holds for the theme settings you use.  Tell me. Let's improve the defaults.

5. Help! I don't see `text/html` content!

    better: How do I properly set up an inline renderer for `text/html`?
    Try `w3m <http://w3m.sourceforge.net/>`_ and put the following into your
    :file:`~/.mailcap`::

        text/html;  w3m -dump -o document_charset=%{charset} '%s'; nametemplate=%s.html; copiousoutput

    Most `text based browsers <http://en.wikipedia.org/wiki/Text-based_web_browser>`_ have
    a dump mode that can be used here.

6. Why are you doing $THIS not $THAT way?

    Lazyness and Ignorance: In most cases I simply did not or still don't know a better solution.
    I try to outsource as much as I can to well established libraries and be it only to avoid
    having to read rfc's. But there are lots
    of tasks I implemented myself, possibly overlooking a ready made and available solution.
    Twisted is such a feature-rich but gray area in my mind for example.
    If you think you know how to improve the current implementation let me know!

    The few exceptions to above stated rule are the following:

    * The modules cmd and cmd2, that handle all sorts of convenience around command objects
      hate urwid: They are painfully strongly coupled to user in/output via stdin and out.
    * `notmuch reply` is not used to format reply messages because 1. it is not offered by
      notmuch's library but is a feature of the CLI. This means we would have to call the notmuch
      binary, something that is avoided where possible. 2. As there is no `notmuch forward` equivalent,
      this (very similar) functionality would have to be re-implemented anyway.

.. _faq_7:

7. I thought alot ran on Python 2?

   It used to. When we made the transition to Python 3 we didn't maintain
   Python 2 support. If you still need Python 2 support the 0.7 release is your
   best bet.

