#!/usr/bin/env python
import subprocess
import re
import sys
import textwrap

from setuptools import setup

import alot


# Install deps automagically if they're not already installed.  If you're 
# queezy, imagine that instead of this nasty block there was a pretty ASCII art
# picture of a kitty here.

# Use install_requires, which will automatically install deps from PyPI
# when setup.py is run
install_requires = [
    "ConfigObj>=4.6.0",
    "PyGPGME",
    "Twisted>=10.2.0",
    "urwid>=1.1.0",
]

# There is an unofficial and an official set of bindings for libmagic, and they
# are not 100% API compatiple. We depend on the official ones, but the
# unofficial ones are the ones currently on PyPI. So if `magic` (which might be
# the official) is present already, skip installing python-magic
try:
    import magic
except ImportError:
    install_requires.append("python-magic")

# libnotmuch must have its Python bindings match the version of libnotmuch
# that's installed. So check the version of libnotmuch by running
# `notmuch --version` and grab that version of the bindings.
try:
    notmuch = subprocess.check_output(["notmuch", "--version"])
except OSError:
    msg = textwrap.dedent("""
        Installing alot requires notmuch. See the installation instructions at 
        http://alot.readthedocs.org/en/latest/installation.html for details.
    """)
    sys.exit(msg)
else:
    # output looks like notmuch X.Y.Z, possibly with a dev version tacked on
    notmuch_version = re.search(r"\d+\.\d+(\.\d+)?", notmuch)
    if notmuch_version is not None:
        install_requires.append("notmuch==%s" % notmuch_version.group(0))


setup(name='alot',
      version=alot.__version__,
      description=alot.__description__,
      author=alot.__author__,
      author_email=alot.__author_email__,
      url=alot.__url__,
      license=alot.__copyright__,
      packages=['alot', 'alot.commands', 'alot.settings', 'alot.db',
                'alot.utils', 'alot.widgets', 'alot.foreign', 'alot.foreign.urwidtrees'],
      package_data={'alot': [
                             'defaults/alot.rc.spec',
                             'defaults/notmuch.rc.spec',
                             'defaults/abook_contacts.spec',
                             'defaults/default.theme',
                             'defaults/default.bindings',
                             'defaults/config.stub',
                             'defaults/theme.spec',
                            ]},
      scripts=['bin/alot'],
      install_requires=install_requires,
      requires=[
        'notmuch (>=0.13)',
        'argparse (>=2.7)',
        'urwid (>=1.1.0)',
        'twisted (>=10.2.0)',
        'magic',
        'configobj (>=4.6.0)',
        'subprocess (>=2.7)',
        'gpgme (>=0.2)'],
      provides=['alot'],
)
