#!/usr/bin/env python

from distutils.core import setup
import alot



setup(name='alot',
      version=alot.version.read_version(),
      description=alot.__description__,
      author=alot.__author__,
      author_email=alot.__author_email__,
      url=alot.__url__,
      packages=['alot', 'alot.commands'],
      package_data={'alot': ['defaults/alot.rc', 'defaults/notmuch.rc',
          'VERSION']},
      scripts=['bin/alot'],
      license=alot.__copyright__,
      requires=[
        'notmuch (>=0.9)',
        'argparse (>=2.7)',
        'urwid (>=1.0)',
        'twisted (>=10.2.0)',
        'magic',
        'subprocess (>=2.7)'],
      provides='alot',
)
