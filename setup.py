#!/usr/bin/env python

from distutils.core import setup
import alot

setup(name='alot',
      version=alot.__version__,
      description=alot.__description__,
      author=alot.__author__,
      author_email=alot.__author_email__,
      url=alot.__url__,
      packages=['alot'],
      package_data={'alot': ['defaults/alot.rc', 'defaults/notmuch.rc']},
      scripts=['bin/alot'],
      license=alot.__copyright__,
      requires=[
        'notmuch (>=0.7.1)',
        'argparse (>=2.7)',
        'urwid (>=1.0)',
        'subprocess (>=2.7)'],
      provides='alot'
)

