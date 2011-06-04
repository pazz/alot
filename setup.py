#!/usr/bin/env python

from distutils.core import setup
import alot

setup(name = "alot",
      version = alot.__version__,
      description = alot.__description__,
      author = alot.__author__,
      author_email = alot.__author_email__,
      url = alot.__url__,
      packages = ['alot'],
      scripts = ['bin/alot'],
      license = alot.__copyright__
      install_requires = ['notmuch>=0.4',
                          'urwid']
)

