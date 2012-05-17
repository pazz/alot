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
      packages=['alot', 'alot.commands', 'alot.settings', 'alot.db'],
      package_data={'alot': [
                             'defaults/alot.rc.spec',
                             'defaults/notmuch.rc.spec',
                             'defaults/abook_contacts.spec',
                             'defaults/default.theme',
                             'defaults/config.stub',
                             'defaults/theme.spec',
                            ]},
      scripts=['bin/alot'],
      requires=[
        'notmuch (>=0.13)',
        'argparse (>=2.7)',
        'urwid (>=1.0)',
        'twisted (>=10.2.0)',
        'magic',
        'configobj (>=4.6.0)',
        'subprocess (>=2.7)',
        'pyme (>=0.8.1)'],
      provides='alot',
)
