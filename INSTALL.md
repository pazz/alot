INSTALL
=======

Alot depends on development versions of notmuch and urwid. Note that due to restrictions
on argparse and subprocess, you need to run *python v>=2.7*, which only recently made it
into debian testing.

urwid
-----
make sure you have urwid v >=1.0. It is available on debian (wheezy)
and in *buntu 12.04. To install from git use:

    git clone http://github.com/wardi/urwid
    cd urwid
    sudo python setup.py install

It seems you need the python headers for this. On debian/ubuntu:

    aptitude install python2.7-dev


notmuch
-------
install notmuch *and* python bindings from git:

    git clone git://notmuchmail.org/git/notmuch

    cd notmuch
    ./configure
    make
    sudo make install
    cd bindings/python
    sudo python setup.py install


alot
----
get alot and install it from git:

    git clone git://github.com/pazz/alot alot
    cd alot
    sudo python setup.py install

That's it, now `alot` should be in your path.

Alot tries to be as unobtrusive as possible, with one exception: It forces you to use
UTF-8 encoding whereever it can: All text parts and headers of outgoing emails are
converted to utf-8, notmuch tagstrings, edited emails and config files are interpreted as
Utf-8.

All configs are optional, but if you want to send mails you need to specify at least one
account section in your config:

    [account uoe]
    realname = Your Name
    address = your@address

See `CUSTOMIZE.md` on how to do fancy customization.
