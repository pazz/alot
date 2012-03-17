Installation
************

Alot depends on recent versions of notmuch and urwid. Note that due to restrictions
on argparse and subprocess, you need to run *python ≥ `2.7`*.
A full list of dependencies is below:

* `libmagic and python bindings <http://darwinsys.com/file/>`_, ≥ `5.04`:
* `configobj <http://www.voidspace.org.uk/python/configobj.html>`_, ≥ `4.6.0`:
* `twisted <http://twistedmatrix.com/trac/>`_, ≥ `10.2.0`:
* `libnotmuch <http://notmuchmail.org/>`_ and it's python bindings, ≥ `0.11`.
* `urwid <http://excess.org/urwid/>`_ toolkit, ≥ `1.0`


On debian/ubuntu these are packaged as::

  python-magic python-configobj python-twisted python-notmuch python-urwid

Grab a copy of `alot` `here <https://github.com/pazz/alot/tags>`_ or
directly check out a more recent version from `github <https://github.com/pazz/alot>`_.
Run the :file:`setup.py` like this to install locally::

    python setup.py install --user

and make sure :file:`~/.local/bin` is in your :envvar:`PATH`.

Alot uses mailcap to look up mime-handler for inline rendering and opening of attachments.
For a full description of the maicap protocol consider the manpage :manpage:`mailcap(5)`.
