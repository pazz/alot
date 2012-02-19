#!/usr/bin/env python

from distutils.core import setup
import alot


setup(name='alot',
      version=alot.__version__,
      description=alot.__description__,
      author=alot.__author__,
      author_email=alot.__author_email__,
      url=alot.__url__,
      license=alot.__copyright__,
      packages=['alot', 'alot.commands'],
      package_data={'alot': [
                             'defaults/alot.rc', # only old-style default values
                             'defaults/alot.rc.new',
                             'defaults/alot.rc.spec',
                             'defaults/notmuch.rc.spec',
                             'defaults/default.theme', # default theme
                             'defaults/bindings',
                             'defaults/theme.spec',
                            ]},
      scripts=['bin/alot'],
      requires=[
        'notmuch (>=0.9)',
        'argparse (>=2.7)',
        'urwid (>=1.0)',
        'twisted (>=10.2.0)',
        'magic',
        'configobj',
        'subprocess (>=2.7)'],
      provides='alot',
)
