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


All configs are optional, but if you want to send mails you need to specify at least one
:ref:`account <account>` in your config. See the :ref:`configuration <configuration>` for how to do
fancy customization.

You do need to set an inline renderer for text/html in your :file:`~/.mailcap` to display
html mails::
   
       text/html;  w3m -dump %s; nametemplate=%s.html; copiousoutput


