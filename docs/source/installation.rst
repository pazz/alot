Installation
************

These days, alot can be installed directly using your favourite package manager.
On a recent Debian (-derived) systems for instance, just do `sudo apt install alot` and you're done.

.. note::
   Alot uses `mailcap <https://en.wikipedia.org/wiki/Mailcap>`_ to look up mime-handler for inline
   rendering and opening of attachments.
   To avoid surprises you should at least have an inline renderer
   (copiousoutput) set up for `text/html` in your :file:`~/.mailcap`::

     text/html;  w3m -dump -o document_charset=%{charset} '%s'; nametemplate=%s.html; copiousoutput

   On more recent versions of w3m, links can be parsed and appended with reference numbers::

     text/html;  w3m -dump -o document_charset=%{charset} -o display_link_number=1 '%s'; nametemplate=%s.html; copiousoutput

   See the manpage :manpage:`mailcap(5)` or :rfc:`1524` for more details on your mailcap setup.


Manual installation
-------------------

Alot depends on recent versions of notmuch and urwid. Note that due to restrictions
on argparse and subprocess, you need to run *python ≥ 3.5* (see :ref:`faq <faq_7>`).
A full list of dependencies is below:

* `libmagic and python bindings <https://darwinsys.com/file/>`_, ≥ `5.04`
* `configobj <http://www.voidspace.org.uk/python/configobj.html>`_, ≥ `4.7.0`
* `libnotmuch <https://notmuchmail.org/>`_ and it's python bindings, ≥ `0.30`
* `urwid <https://urwid.org/>`_ toolkit, ≥ `1.3.0`
* `urwidtrees <https://github.com/pazz/urwidtrees>`_, ≥ `1.0.3`
* `gpg <https://www.gnupg.org/related_software/gpgme>`_ and it's python bindings, > `1.10.0`
* `twisted <https://twistedmatrix.com>`_, ≥ `18.4.0`


On Debian/Ubuntu these are packaged as::

  python3-setuptools python3-magic python3-configobj python3-notmuch python3-urwid python3-urwidtrees python3-gpg python3-twisted python3-dev swig

On Fedora/Redhat these are packaged as::

  python-setuptools python-magic python-configobj python-notmuch python-urwid python-urwidtrees python-gpg python-twisted


To set up and install the latest development version::

  git clone https://github.com/pazz/alot
  python3 -m venv dev-venv
  . dev-venv/bin/activate
  pip install -e .

or you can install the development version into :file:`~/.local/bin`::

  pip install --user .

Make sure :file:`~/.local/bin` is in your :envvar:`PATH`. For system-wide
installation omit the `--user` flag and call with the respective permissions.


Generating the Docs
-------------------

This requires `sphinx <https://www.sphinx-doc.org/>`_, ≥ `1.3` to be installed.
To generate the documentation from the source directory simply do::

  make -C docs html

A man page can be generated using::

  make -C docs man

Both will end up in their respective subfolders in :file:`docs/build`.

In order to remove the command docs and automatically re-generate them from inline docstrings, use the make target `cleanall`, as in::

  make -C docs cleanall html
