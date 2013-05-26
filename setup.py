#!/usr/bin/env python

try:
    from setuptools import setup
    has_setuptools = True
except ImportError
    from distutils.core import setup
    has_setuptools = False

import alot


more_setup_args = {}

if has_setuptools:
    more_setup_args["install_requires"] = [
        "ConfigObj>=4.6.0",
        "PyGPGME",
        "python-magic",
        "Twisted>=10.2.0",
        "urwid>=1.1.0",
    ]

    try:
        import argparse
    except ImportError:
        more_setup_args["install_requires"].append("argparse")

    import subprocess
    try:
        notmuch = subprocess.Popen(
            ["notmuch", "--version"], stdout=subprocess.PIPE,
        )
    except OSError:
        # notmuch wasn't found, so do nothing. Maybe the user wants to install
        # it later
        pass
    else:
        _, _, notmuch_version = notmuch.stdout.read().rpartition(" ")
        more_setup_args["install_requires"].append(
            "notmuch==%s" % (notmuch_version,)
        )


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
