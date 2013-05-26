#!/usr/bin/env python
import subprocess

import alot

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
    more_setup_args = {}
else:
    # Install deps automagically if they're not already installed.
    # If you're queezy, imagine that instead of this nasty block there was a
    # pretty ASCII art picture of a kitty here.

    # Use install_requires, which will automatically install deps from PyPI
    # when setup.py is run
    install_requires = [
        "ConfigObj>=4.6.0",
        "PyGPGME",
        "python-magic",
        "Twisted>=10.2.0",
        "urwid>=1.1.0",
    ]

    try:
        import argparse
    except ImportError:
        install_requires.append("argparse")  # Python 2.6

    # libnotmuch must have its Python bindings match the version of libnotmuch
    # that's installed. So check the version of libnotmuch by running
    # `notmuch --version` and grab that version of the bindings.
    try:
        notmuch = subprocess.Popen(
            ["notmuch", "--version"], stdout=subprocess.PIPE,
        )
    except OSError:
        # notmuch (the command, and so probably the lib) wasn't found, so do
        # nothing to install its Python deps. Maybe the user wants to install
        # notmuch later, in which case it'll be up to them to grab the bindings
        # as well.
        pass
    else:
        _, _, notmuch_version = notmuch.stdout.read().rpartition(" ")
        install_requires.append("notmuch==%s" % (notmuch_version,))

    more_setup_args = {"install_requires" : install_requires}


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
      **more_setup_args
)
