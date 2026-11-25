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
on argparse and subprocess, you need to run *python ≥ 3.10* (see :ref:`faq <faq_7>`).
A full list of dependencies is below:

* `libmagic <https://darwinsys.com/file/>`_, ≥ `5.04`, and `python-magic <https://github.com/ahupp/python-magic>`_, ≥ `0.4.12`
* `configobj <http://www.voidspace.org.uk/python/configobj.html>`_, ≥ `5.0.1`
* `libnotmuch <https://notmuchmail.org/>`_ and it's python bindings, ≥ `0.34.2`
* `urwid <https://urwid.org/>`_ toolkit, ≥ `2.2.0` (≥ `3.0.3` on python ≥ 3.14)
* `urwidtrees <https://github.com/pazz/urwidtrees>`_, ≥ `1.1.1`
* `gpg <https://www.gnupg.org/related_software/gpgme>`_ and it's python bindings, > `1.10.0`


On Debian/Ubuntu these are packaged as::

  python3-setuptools python3-magic python3-configobj python3-notmuch2 python3-urwid python3-urwidtrees python3-gpg python3-dev swig

On Fedora/Redhat these are packaged as::

  python-setuptools python-magic python-configobj python-notmuch2 python-urwid python-urwidtrees python-gpg

Distributions may package an older urwidtrees than alot needs; if so, install
urwidtrees from PyPI instead.


From version 0.13 on, releases are published on
`PyPI <https://pypi.org/project/alot/>`_.
The bindings for notmuch and gpg are compiled against the system libraries,
so take them from your distribution and install alot with
`pipx <https://pipx.pypa.io/>`_, letting it see the system packages.
On Debian/Ubuntu::

  sudo apt install pipx python3-notmuch2 python3-gpg python3-magic
  PIPX_DEFAULT_BACKEND=pip pipx install --system-site-packages alot

The other dependencies are then installed from PyPI if the system lacks
them or has too old a version.
(The backend setting matters only if `uv<https://docs.astral.sh/uv/>`_ is installed: in that case pipx then uses it instead of pip by default, and uv tries
to build gpg from source instead of using the system's bindings.)



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

This requires `sphinx <https://www.sphinx-doc.org/>`_ to be installed.
To generate the documentation from the source directory simply do::

  make -C docs html

A man page can be generated using::

  make -C docs man

Both will end up in their respective subfolders in :file:`docs/build`.

In order to remove the command docs and automatically re-generate them from inline docstrings, use the make target `cleanall`, as in::

  make -C docs cleanall html
